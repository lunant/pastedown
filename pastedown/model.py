import re
import htmlentitydefs
from google.appengine.ext import db
import markdown2
import vlaah
import vlaah.gae.db as vdb


def vlaah_session(file=None):
    """Creates a VLAAH session instance."""
    import ConfigParser
    from os.path import join, dirname
    conf = ConfigParser.ConfigParser()
    conf.read(file or join(dirname(__file__), "vlaah_session.ini"))
    try:
        settings = conf.items("vlaah_session")
    except ConfigParser.NoSectionError:
        raise IOError("copy pastedown/vlaah_session.ini.dist to "
                      "pastedown/vlaah_session.ini")
    return vlaah.Session(**dict(settings))


VLAAH = vlaah_session()
MARKDOWN = markdown2.Markdown(extras=["footnotes"])


class Document(db.Model):
    """Documents written in Markdown."""

    author = vdb.PersonProperty(VLAAH, indexed=True)
    updated_at = db.DateTimeProperty(auto_now=True)

    @classmethod
    def get_by_author(cls, author):
        """Returns documents written by the author."""
        return cls.all().filter("author = ", author)

    def __init__(self, *args, **kwargs):
        if "body" in kwargs:
            self._body_text = kwargs["body"]
        db.Model.__init__(self, *args, **kwargs)

    @property
    def current_revision(self):
        """The current revision. None when there is no revision."""
        return self.revisions.order("-created_at").get()

    def body(self):
        """Body string of the document's current revision."""
        body = self.current_revision
        return body and unicode(body)

    body = property(
        fget=body,
        fset=lambda self, v: Revision(parent=self, document=self, body=v).put()
    )

    @property
    def html(self):
        """Returns the HTML string of its body."""
        body = self.current_revision
        return body and body.html

    @property
    def title(self):
        body = self.current_revision
        return body and body.title

    def put(self, skip_body=False):
        key = db.Model.put(self)
        if not skip_body and hasattr(self, "_body_text"):
            self.body = self._body_text
            del self._body_text
        return key

    def __unicode__(self):
        return self.title or u""


class Revision(db.Model):
    """Document revisions."""

    TITLE_PATTERN = re.compile(ur"<h1(\s[^>]*)?>(?P<title>.+?)</h1>")
    FIRST_SENTENCE_PATTERN = re.compile(ur"^(?:[^?.]|\.[A-Z])+\??")
    TITLE_MAX_LENGTH = 30
    TITLE_ELLIPSIS = u"\u2026"

    document = db.ReferenceProperty(Document, required=True,
                                    collection_name="revisions", indexed=True)
    body = db.TextProperty(required=True)
    created_at = db.DateTimeProperty(required=True, auto_now_add=True)

    @property
    def html(self):
        """Returns the HTML string of its body."""
        return self.body and MARKDOWN.convert(self.body)

    @property
    def title(self):
        """Title of the document. It is from its first <h1> text or its first
        some text.

        """
        def strip_html(html):
            html = re.sub(ur"<[^>]+>", u"", html)
            map = htmlentitydefs.name2codepoint
            return re.sub(
                ur"&(?:#([0-9a-fA-F]+)|(\w+));",
                lambda m: unichr(map[m.group(2)] if m.group(2)
                                                 else int(m.group(1), 16)),
                html
            )
        match = self.TITLE_PATTERN.search(self.html)
        if match:
            return strip_html(match.group("title"))
        text = strip_html(self.html)
        match = self.FIRST_SENTENCE_PATTERN.match(text)
        text = match.group(0) if match else text
        if len(text) > self.TITLE_MAX_LENGTH:
            length = self.TITLE_MAX_LENGTH - len(self.TITLE_ELLIPSIS)
            text = text[0:length] + self.TITLE_ELLIPSIS
        return text

    def put(self):
        def put_it():
            doc = self.document
            doc.updated_at = self.created_at
            doc.put(True)
            db.Model.put(self)
        db.run_in_transaction(put_it)
        return self.key()

    def __unicode__(self):
        return unicode(self.body) or u""


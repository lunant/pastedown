import re
import datetime
import itertools
import hashlib
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

    KEY_NAME_LENGTH_RANGE = 6, 32

    author = vdb.PersonProperty(VLAAH, indexed=True)
    updated_at = db.DateTimeProperty(auto_now=True)

    @classmethod
    def create_key_name(cls, person=None, id=None):
        """Creates a new unique key_name for documents."""
        person_name = person.name + "/" if person else ""
        if isinstance(id, basestring):
            return person_name + id
        elif not callable(id) and id is not None:
            raise TypeError("id must be callable or a string; %s given"
                            % type(id).__name__)
        min, max = cls.KEY_NAME_LENGTH_RANGE
        lengths = itertools.chain(xrange(min, max), itertools.repeat(max))
        if id:
            lengths = itertools.chain([0], lengths)
        for l in lengths:
            hash = hashlib.sha512(str(datetime.datetime.now()))
            hash = hash.hexdigest()[:l]
            key_name = id(hash) if id else hash
            if key_name == "":
                continue
            key_name = cls.create_key_name(person, key_name)
            if not cls.get_by_key_name(key_name):
                return key_name

    @classmethod
    def get_by_author(cls, author):
        """Returns documents written by the author."""
        if isinstance(author, vlaah.Person):
            return cls.all().filter("author = ", author.name)
        typename = type(author).__name__
        raise TypeError("author must be a Person instance, not " + typename)

    @classmethod
    def find(cls, author, id):
        key_name = cls.create_key_name(author, id)
        return cls.get_by_key_name(key_name)

    def __init__(self, *args, **kwargs):
        if "body" in kwargs:
            self._body_text = kwargs["body"]
        if "key_name" not in kwargs and "key" not in kwargs:
            if "body" in kwargs and "author" in kwargs and kwargs["author"]:
                html = MARKDOWN.convert(kwargs["body"])
                title = create_title(html) or ""
                title = title.replace(TITLE_ELLIPSIS, "")
                slug = re.sub(ur"\W+", ur"-",
                              re.sub(ur"^\W+|\W+$", ur"", title)).lower()
                def id(name):
                    if not slug:
                        return name
                    return slug + "-" + name if name and slug else slug
            else:
                id = None
            key_name = self.create_key_name(kwargs["author"], id)
            kwargs["key_name"] = key_name
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

    def is_modifiable(self, person):
        """Returns True when the document is modifiable by the person."""
        if isinstance(person, vlaah.Person):
            if self.author is None:
                return False
            return self.author.normal_name == person.normal_name
        elif person is None:
            return False
        typ = type(person).__name__
        raise TypeError("person must be a vlaah.Person instance, not " + typ)

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

    UNTITLED = "(Untitled)"

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
        """Title of the document."""
        return create_title(self.html) or self.UNTITLED

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


TITLE_PATTERN = re.compile(ur"<h1(\s[^>]*)?>\s*(?P<title>.+?)\s*</h1>")
FIRST_SENTENCE_PATTERN = re.compile(ur"^(?:[^?.]|\.[A-Z])+\??")
TITLE_MAX_LENGTH = 30
TITLE_ELLIPSIS = u"\u2026"


def create_title(html):
    """Title of the HTML document. It is from its first <h1> text or its first
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
    match = TITLE_PATTERN.search(html)
    if match:
        return strip_html(match.group("title")) or None
    text = strip_html(html)
    match = FIRST_SENTENCE_PATTERN.match(text)
    text = match.group(0) if match else text
    if len(text) > TITLE_MAX_LENGTH:
        length = TITLE_MAX_LENGTH - len(TITLE_ELLIPSIS)
        text = text[0:length] + TITLE_ELLIPSIS
    return text or None


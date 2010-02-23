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

    def __unicode__(self):
        return self.body


class Revision(db.Model):
    """Document revisions."""

    document = db.ReferenceProperty(Document, required=True,
                                    collection_name="revisions", indexed=True)
    body = db.TextProperty(required=True)
    created_at = db.DateTimeProperty(required=True, auto_now_add=True)

    @property
    def html(self):
        """Returns the HTML string of its body."""
        return self.body and MARKDOWN.convert(self.body)

    def put(self):
        def put_it():
            db.Model.put(self)
            doc = self.document
            doc.updated_at = self.created_at
            doc.put()
        db.run_in_transaction(put_it)
        return self.key()

    def __unicode__(self):
        return unicode(self.body)


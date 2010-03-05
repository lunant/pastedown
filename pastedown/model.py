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

    parent_document = db.SelfReferenceProperty(collection_name="forks")
    parent_revision = db.ReferenceProperty()
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
        if not kwargs.get("_from_entity", False):
            if "body" in kwargs:
                self._body_text = kwargs["body"]
            if "parent_document" in kwargs and kwargs["parent_document"]:
                parent_document = kwargs["parent_document"]
                kwargs["parent_revision"] = parent_document.current_revision
            elif "parent_revision" in kwargs and kwargs["parent_revision"]:
                kwargs["parent_document"] = kwargs["parent_revision"].document
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
    def revisions(self):
        """Returns the set of revisions."""
        return RevisionSet(self)

    @property
    def current_revision(self):
        """The current revision. None when there is no revision."""
        for rev in self.revisions:
            return rev

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
        """The title picked from its current first sentence or <h1>."""
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

    def fork(self, author, body):
        """Fork the document."""
        if author is not None and not isinstance(author, vlaah.Person):
            raise TypeError("author must be a vlaah.Person instance, not "
                            + type(author).__name__)
        elif not isinstance(body, basestring):
            raise TypeError("body is not a string, but " + type(body).__name__)
        return type(self)(parent_document=self, author=author, body=body)

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
                                    collection_name="overriding_revisions",
                                    indexed=True)
    body = db.TextProperty(required=True)
    created_at = db.DateTimeProperty(required=True, auto_now_add=True)

    @property
    def author(self):
        """Returns the author."""
        return (self.parent() or self.document).author

    @property
    def html(self):
        """Returns the HTML string of its body."""
        return self.body and MARKDOWN.convert(self.body)

    @property
    def title(self):
        """Title of the document."""
        return create_title(self.html) or self.UNTITLED

    def fork(self, author, body):
        """Forks the document from this revision."""
        if author is not None and not isinstance(author, vlaah.Person):
            raise TypeError("author must be a vlaah.Person instance, not "
                            + type(author).__name__)
        elif not isinstance(body, basestring):
            raise TypeError("body is not a string, but " + type(body).__name__)
        return Document(parent_revision=self, author=author, body=body)

    @property
    def forks(self):
        """Returns forked documents."""
        return Document.all().filter("parent_revision =", self)

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


class RevisionSet(object):
    """The set of revisions."""

    def __init__(self, document):
        if not isinstance(document, Document):
            typename = type(document).__name__
            raise TypeError("expected a Document instance, not " + typename)
        self.document = document

    def query_hierarchy(self):
        document = self.document
        before = None
        while document:
            revisions = document.overriding_revisions
            if before:
                revisions = revisions.filter("created_at <=", before)
            yield revisions.order("-created_at")
            revision = document.parent_revision
            document = document.parent_document
            if document and revision:
                before = revision.created_at

    def count(self, limit=None):
        """Returns the number of revisions in the set."""
        cnt = 0
        if limit is not None and limit <= 0:
            return 0
        for revision_set in self.query_hierarchy():
            cnt += revision_set.count(limit or 1000)
            if limit is not None and limit - cnt <= 0:
                return cnt
        return cnt

    def __getitem__(self, key):
        """Finds the revision by the created time or the offset number."""
        if isinstance(key, (datetime.datetime, datetime.date)):
            for revision_set in self.query_hierarchy():
                for revision in revision_set.filter("created_at =", key):
                    return revision
            raise KeyError("no revision created at %r" % key)
        elif isinstance(key, (int, long)):
            if key < 0:
                cnt = self.count() + key
            for revision_set in self.query_hierarchy():
                cnt = revision_set.count(key + 1)
                if cnt > key:
                    return revision_set.fetch(1, key)[0]
                key -= cnt
            raise IndexError("set index out of range %r" % key)
        raise TypeError("key must be a datetime.date, datetime.datetime, "
                        "int or long instance, not " + type(key).__name__)

    def __iter__(self):
        for revision_set in self.query_hierarchy():
            for revision in revision_set:
                yield revision

    def __len__(self):
        return self.count()


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


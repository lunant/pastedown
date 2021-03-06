import datetime
import hashlib
import urllib
from google.appengine.ext import webapp, db
from google.appengine.api import memcache
import beaker.middleware
import jinja2
import vlaah
from recaptcha.client import captcha
import pastedown
from pastedown.model import *
from pastedown.appext import WSGIApplication
from pastedown.template import ENVIRONMENT as VIEW_ENV


BEAKER_SESSION_OPTIONS = {
    "session.type": "ext:google",
    "session.auto": True,
    "session.cookie_expires": True,
    "session.key": "pastedown_session",
    "session.secret": VLAAH.appkey
}


def _session_setter(name, map):
    def fset(self, value):
        if value is None:
            del self.session[name]
        else:
            self.session[name] = map(value)
    return fset


def captcha_submit(request):
    """Submits the CAPTCHA input."""
    return captcha.submit(request.get("recaptcha_challenge_field", ""),
                          request.get("recaptcha_response_field", ""),
                          pastedown.configuration("recaptcha")["private_key"],
                          request.remote_addr)


class BaseHandler(webapp.RequestHandler):

    @property
    def session(self):
        """Beaker session object."""
        return self.request.environ["beaker.session"]

    def person(self):
        """Signed person."""
        if "person_name" in self.session and self.session["person_name"]:
            topic = VLAAH.find(self.session["person_name"])
            if isinstance(topic, vlaah.Person):
                return topic

    person = property(
        fget=person,
        fset=_session_setter("person_name", lambda person: person.name)
    )

    def ticket(self):
        """Allowed ticket."""
        if "ticket_id" in self.session and self.person:
            ticket_id = self.session["ticket_id"]
            if ticket_id:
                try:
                    return self.person.tickets[ticket_id]
                except KeyError:
                    del self.session["ticket_id"]
                    return

    ticket = property(
        fget=ticket,
        fset=_session_setter("ticket_id", lambda ticket: ticket.id)
    )

    def render(self, template, **kwargs):
        t = VIEW_ENV.get_template(template)
        view = t.generate(handler=self,
                          person=self.person,
                          ticket=self.ticket,
                          **kwargs)
        for part in view:
            self.response.out.write(part)


class HomeHandler(BaseHandler):

    NUMBER_TO_FETCH = 10

    def get(self, body=None, captcha_response=None):
        docs = Document.all().filter("updated_at != ", None) \
                             .order("-updated_at") \
                             .fetch(self.NUMBER_TO_FETCH)
        self.render("home.html", documents=docs,
                                 body=body,
                                 captcha_response=captcha_response)

    def post(self):
        """Post a new document."""
        person = self.person
        body = self.request.get("body")
        if not person:
            response = captcha_submit(self.request)
            if not response.is_valid:
                return self.get(body=body, captcha_response=response)
        doc = Document(author=self.person, body=body)
        doc.put()
        self.redirect("/" + doc.key().name())


class LoginHandler(BaseHandler):

    MEMCACHE_NAMESPACE = "loginkey"

    def get(self):
        name = self.request.get("person")
        key = self.request.get("key")
        back = self.request.get("destination")
        person = VLAAH.find(name)
        ticket = person.tickets[memcache.get(key, self.MEMCACHE_NAMESPACE)]
        self.ticket = ticket
        self.person = person
        self.redirect(back)

    def post(self):
        name = self.request.get("name")
        back = self.request.get("destination", self.request.referer or "/")
        ns = self.MEMCACHE_NAMESPACE
        if "@" in name:
            topic = VLAAH.find(name)
            person = hasattr(topic, "person") and topic.person
        else:
            name = name if name[0] == "~" else "~" + name
            person = VLAAH.find(name)
        if isinstance(person, vlaah.Person):
            ip = self.request.remote_addr
            while True:
                key = hashlib.md5("%s %s" % (ip, datetime.datetime.now()))
                key = key.hexdigest()
                if not memcache.get(key, ns):
                    break
            memcache.set(key, "", 1800)
            url = self.request.url
            return_to = "%s?person=%s&key=%s&destination=%s" % \
                        (url, person.name, key, urllib.quote(back))
            ticket = person.tickets.create(destination=return_to)
            memcache.set(key, ticket.id, 3600, namespace=ns)
            self.redirect(ticket.url)
        else:
            back += ("&" if "?" in back else "?") + "__login_error__=1"
            self.redirect(back)

    def delete(self):
        back = self.request.get("destination", self.request.referer or "/")
        self.person = None
        self.ticket = None
        self.redirect(back)


class PersonHandler(BaseHandler):

    def get(self, person):
        author = VLAAH.find("~" + person)
        if not isinstance(author, vlaah.Person):
            self.error(404)
            return
        documents = Document.get_by_author(author)
        self.render("person.html", author=author, documents=documents)


class DocumentHandler(BaseHandler):
    REVISION_PATTERN = re.compile(r"^(\d{4})/(\d\d)/(\d\d)/"
                                  r"(\d\d)(\d\d)(\d\d)\.(\d+)$")
    HTML_MIMES = "text/html",
    TEXT_MIMES = "text/x-markdown", "text/plain"
    MIMES = TEXT_MIMES + HTML_MIMES

    def find_document(self, person, id):
        """Finds the document. Responds as 404 when the document is not
        found.

        """
        if person:
            person = VLAAH.find("~" + person)
            if not isinstance(person, vlaah.Person):
                self.error(404)
                return
        else:
            person = None
        document = Document.find(person, id)
        if not document:
            self.error(404)
            return
        return document

    def find_revision(self, document, revision):
        if revision:
            if not isinstance(revision, Revision):
                if not isinstance(revision, datetime.datetime):
                    revision = self.REVISION_PATTERN.match(revision)
                    revision = datetime.datetime(*map(int, revision.groups()))
                revision = document.revisions[revision]
        else:
            revision = document.current_revision
        return revision

    def assert_modifiability(self, document):
        if not document.is_modifiable(self.person):
            self.error(403)
            self.render("document.not_modifiable.html",
                        document=document, revision=document.current_revision)
            return False
        return True

    def get(self, person, id,
            revision=None, document=None,
            forking_body=None, captcha_response=None):
        self.response.headers["Vary"] = "Accept"
        document = document or self.find_document(person, id)
        revision = self.find_revision(document, revision)
        if document:
            mime = self.request.accept.best_match(self.MIMES)
            if not mime:
                self.error(406)
                return
            self.response.headers["Content-Type"] = mime + "; charset=utf-8"
            if mime in self.HTML_MIMES:
                self.render("document.html",
                            document=document, revision=revision,
                            mime=mime, xhtml=mime == "application/xhtml+xml",
                            forking_body=forking_body,
                            captcha_response=captcha_response)
            elif mime in self.TEXT_MIMES:
                self.response.out.write(revision.body.encode("utf-8"))

    def put(self, person, id):
        document = self.find_document(person, id)
        if not (document and self.assert_modifiability(document)):
            return
        document.body = self.request.get("body")
        self.get(person, id, document=document)

    def post(self, person, id, revision=None):
        document = self.find_document(person, id)
        revision = self.find_revision(document, revision)
        if not document:
            return
        body = self.request.get("body")
        author = self.person
        if not author:
            response = captcha_submit(self.request)
            if not response.is_valid:
                return self.get(person, id,
                                forking_body=body, captcha_response=response)
        doc = revision.fork(author=author, body=body)
        doc.put()
        self.redirect("/" + doc.key().name())

    def delete(self, person, id):
        document = self.find_document(person, id)
        if not (document and self.assert_modifiability(document)):
            return
        document.delete()
        self.redirect("/~%s/" % person)


application = beaker.middleware.SessionMiddleware(
    WSGIApplication([
        (r"/", HomeHandler),
        (r"/login/?", LoginHandler),
        (r"/(?:%7[Ee]|~)(?P<person>[-_.a-z0-9]{3,32})/?", PersonHandler),
        (r"/(?P<person>)(?P<id>[^~/][^/]{5,})/?", DocumentHandler),
        (r"/(?P<person>)(?P<id>[^~/][^/]{5,})"
         r"/(?P<rev>\d{4}/\d\d/\d\d/\d{6}.\d+)", DocumentHandler),
        (r"/(?:%7[Ee]|~)(?P<person>[-_.a-z0-9]{3,32})/(?P<id>[^/]+)/?",
         DocumentHandler),
        (r"/(?:%7[Ee]|~)(?P<person>[-_.a-z0-9]{3,32})/(?P<id>[^/]+)"
         r"/(?P<rev>\d{4}/\d\d/\d\d/\d{6}.\d+)", DocumentHandler),
    ], debug=True),
    BEAKER_SESSION_OPTIONS
)


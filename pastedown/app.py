import os.path
import datetime
import hashlib
import urllib
from google.appengine.ext import webapp, db
from google.appengine.api import memcache
import beaker.middleware
import jinja2
import vlaah
from pastedown.model import *
from pastedown.appext import WSGIApplication


VIEW_PATH = os.path.join(os.path.dirname(__file__), "views")
VIEW_LOADER = jinja2.FileSystemLoader(VIEW_PATH)
VIEW_ENV = jinja2.Environment(loader=VIEW_LOADER)

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

    def get(self):
        docs = Document.all().filter("updated_at != ", None) \
                             .order("-updated_at")
        self.render("home.html", documents=docs)

    def post(self):
        """Post a new document."""
        person = self.person
        doc = Document(key_name=Document.create_key_name(person),
                       author=self.person, body=self.request.get("body"))
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

    def delete(self):
        back = self.request.get("destination", self.request.referer or "/")
        self.person = None
        self.ticket = None
        self.redirect(back)


class DocumentHandler(BaseHandler):

    def get(self, person, id):
        if person:
            person = VLAAH.find("~" + person)
            if not isinstance(person, vlaah.Person):
                self.error(404)
        else:
            person = None
        document = Document.find(person, id)
        if not document:
            self.error(404)
        self.response.out.write(document.html)


application = beaker.middleware.SessionMiddleware(
    WSGIApplication([
        ("/", HomeHandler),
        ("/login/?", LoginHandler),
        ("/(?P<person>)(?P<id>[^~/][^/]{5,})", DocumentHandler),
        ("/(?:%7[Ee]|~)(?P<person>[-_.a-z0-9]{3,32})/(?P<id>[^/]{6,})",
         DocumentHandler),
    ], debug=True),
    BEAKER_SESSION_OPTIONS
)


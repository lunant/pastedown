import os.path
from google.appengine.ext import webapp
from google.appengine.ext import db
import jinja2
from pastedown.model import *


VIEW_PATH = os.path.join(os.path.dirname(__file__), "views")
VIEW_LOADER = jinja2.FileSystemLoader(VIEW_PATH)
VIEW_ENV = jinja2.Environment(loader=VIEW_LOADER)


class HomeHandler(webapp.RequestHandler):

    def get(self):
        docs = Document.all().filter("updated_at != ", None) \
                             .order("-updated_at")
        template = VIEW_ENV.get_template("home.html")
        self.response.out.write(template.render(documents=docs))

    def post(self):
        """Post a new document."""
        doc = Document(body=self.request.get("body"))
        doc.put()
        self.redirect("/" + str(doc.key()))


class DocumentHandler(webapp.RequestHandler):

    def get(self, key):
        document = Document.get(db.Key(key))
        self.response.out.write(document.html)


application = webapp.WSGIApplication([
    ("/", HomeHandler),
    ("/(?P<key>[^~/][^/]*)", DocumentHandler)
], debug=True)


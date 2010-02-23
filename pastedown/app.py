from google.appengine.ext import webapp
from pastedown.model import *


class HomeHandler(webapp.RequestHandler):

    def get(self):
        for doc in Document.all():
            print>>self.response.out, doc.html


application = webapp.WSGIApplication([
    ("/", HomeHandler)
], debug=True)


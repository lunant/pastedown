from google.appengine.ext import webapp


class HomeHandler(webapp.RequestHandler):

    def get(self):
        self.response.out.write("hello?")


application = webapp.WSGIApplication([
    ("/", HomeHandler)
], debug=True)


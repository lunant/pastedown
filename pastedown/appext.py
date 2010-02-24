import sys
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs
from google.appengine.ext import webapp


class WSGIApplication(webapp.WSGIApplication):
    """Patched version of google.appengine.ext.webapp.WSGIApplication."""

    def __call__(self, environ, start_response):
        """Called by WSGI when a request comes in."""
        environ = dict(environ)
        environ["ORIGINAL_REQUEST_METHOD"] = environ["REQUEST_METHOD"]
        if environ["REQUEST_METHOD"].upper() == "POST" and \
           environ["CONTENT_TYPE"] == "application/x-www-form-urlencoded":
            data = sys.stdin.read()
            environ["wsgi.input"] = StringIO.StringIO(data)
            data = parse_qs(data)
            if "__method__" in data:
                environ["REQUEST_METHOD"] = data["__method__"][0].upper()
        return webapp.WSGIApplication.__call__(self, environ, start_response)


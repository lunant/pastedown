import sys
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
try:
    from urlparse import parse_qs, parse_qsl
except ImportError:
    from cgi import parse_qs
import cgi
from google.appengine.ext import webapp
import webob
import webob.multidict as multidict


class Request(webapp.Request):
    """Patched version of google.appengine.ext.webapp.Request."""

    def method(self):
        if hasattr(self, "_method"):
            return self._method
        self._method = self.environ.get("ORIGINAL_REQUEST_METHOD",
                                        self.environ["REQUEST_METHOD"])
        return self._method

    def _method__set(self, method):
        self._method = method.upper()
        self.environ["REQUEST_METHOD"] = method.upper()

    method = property(fget=method, fset=_method__set)

    @property
    def pseudo_method(self):
        return self.environ.get("REQUEST_METHOD")


class WSGIApplication(webapp.WSGIApplication):
    """Patched version of google.appengine.ext.webapp.WSGIApplication."""

    REQUEST_CLASS = Request

    def __call__(self, environ, start_response):
        """Called by WSGI when a request comes in."""
        environ = dict(environ)
        environ["ORIGINAL_REQUEST_METHOD"] = environ["REQUEST_METHOD"]
        if environ["REQUEST_METHOD"].upper() == "POST" and \
           environ["CONTENT_TYPE"] == "application/x-www-form-urlencoded":
            data = environ["wsgi.input"].read()
            environ["wsgi.input"] = StringIO.StringIO(data)
            data = parse_qs(data)
            if "__method__" in data:
                environ["REQUEST_METHOD"] = data["__method__"][0].upper()
        return webapp.WSGIApplication.__call__(self, environ, start_response)


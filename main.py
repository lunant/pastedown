#!/usr/bin/env python
from google.appengine.ext.webapp.util import run_wsgi_app
import pastedown.app


def main():
    run_wsgi_app(pastedown.app.application)


if __name__ == "__main__":
    main()


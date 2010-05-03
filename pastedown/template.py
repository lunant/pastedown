import re
import os.path
import jinja2
import vlaah
from recaptcha.client import captcha
import pastedown
from pastedown.model import *


PATH = os.path.join(os.path.dirname(__file__), "views")
LOADER = jinja2.FileSystemLoader(PATH)
ENVIRONMENT = jinja2.Environment(loader=LOADER)


def global_(function):
    ENVIRONMENT.globals[function.__name__] = function
    return function


def filter(function):
    ENVIRONMENT.filters[function.__name__] = function
    return function


@filter
def url(value):
    if isinstance(value, Document):
        return "/" + value.key().name() + "/"
    elif isinstance(value, Revision):
        dt = value.created_at.strftime("%Y/%m/%d/%H%M%S.") \
           + "%06d" % value.created_at.microsecond
        return url(value.document) + dt
    elif isinstance(value, vlaah.Person):
        return "/" + value.name + "/"

@filter
def remove_query(value, name):
    return re.sub(r"(\?|&)%s=[^&]*(&|$)" % name, r"\1", value)


@global_
def recaptcha(response=None):
    """Builds the ReCAPTCHA HTML."""
    config = pastedown.configuration("recaptcha")
    error = response and response.error_code
    return captcha.displayhtml(config["public_key"], use_ssl=True, error=error)


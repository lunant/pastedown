import os.path
import jinja2
import vlaah
from pastedown.model import *


PATH = os.path.join(os.path.dirname(__file__), "views")
LOADER = jinja2.FileSystemLoader(PATH)
ENVIRONMENT = jinja2.Environment(loader=LOADER)


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


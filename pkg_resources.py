
def iter_entry_points(pkg):
    yield PseudoEntryPoint()


def declare_namespace(name):
    pass


class PseudoEntryPoint(object):

    def __init__(self):
        name = ""

    def load(self):
        raise SyntaxError()


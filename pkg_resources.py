def iter_entry_points(pkg):
    yield PseudoEntryPoint()


class PseudoEntryPoint(object):

    def __init__(self):
        name = ""

    def load(self):
        raise SyntaxError()


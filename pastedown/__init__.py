import ConfigParser
import os.path
import vlaah


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.ini")


def configuration(section, file=None):
    """Reads attributes dict of a section from the configuration file."""
    conf = ConfigParser.ConfigParser()
    file = file or CONFIG_FILE
    conf.read(file)
    try:
        settings = conf.items(section)
    except ConfigParser.NoSectionError:
        raise IOError("copy %s.dist to %s and set it up" % (file, file))
    return dict(settings)


def vlaah_session():
    """Creates a VLAAH session instance."""
    global VLAAH
    try:
        return VLAAH
    except NameError:
        VLAAH = vlaah.Session(**configuration("vlaah"))
    return VLAAH



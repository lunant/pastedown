from distutils.core import setup
from distutils.cmd import Command
from distutils.errors import DistutilsOptionError
import os
import os.path
import tarfile
import urllib2
import hashlib
try:
    import cStringIO as StringIO
except:
    import StringIO


class download_libs(Command):
    """Download external libraries and extract them to working directory."""

    list = "external_libs.txt"
    description = __doc__
    user_options = [("list=", "l", "the filename that contains a list of "
                                   "external libraries' names and source "
                                   "archive urls (default: %s)" % list)]

    def initialize_options(self):
        pass

    def finalize_options(self):
        if not os.path.isfile(self.list):
            raise DistutilsOptionError, "%r does not exist" % self.list

    def get_list(self):
        for line in open(self.list):
            yield tuple(line.split())

    def install_external_lib(self, name, url):
        path = os.path.dirname(__file__)
        file = url[-3:] == ".py"
        if file and os.path.isfile(os.path.join(path, name + ".py")) or \
           os.path.isdir(os.path.join(path, name)):
            return
        urlp = urllib2.urlopen(url)
        if file:
            f = open(name + ".py", "w")
            f.write(urlp.read())
            urlp.close()
            f.close()
            return
        file = StringIO.StringIO(urlp.read())
        urlp.close()
        archive = tarfile.open(fileobj=file)
        try:
            root = min(
                (member for member in archive.getmembers() if member.isdir()),
                key=lambda member: len(member.name)
            )
        except ValueError:
            root = archive.getnames()[0].split("/")[0]
        else:
            root = root.name
        def endslash(path):
            return path if path.endswith("/") else path + "/"
        dir = endslash(root) + endslash(name)
        members = (member for member in archive.getmembers()
                          if member.name.startswith(dir))
        origpath = path
        path = os.path.join(path, hashlib.md5(url).hexdigest())
        os.mkdir(path)
        archive.extractall(path, members)
        archive.close()
        file.close()
        os.rename(os.path.join(path, root, name), os.path.join(origpath, name))
        os.removedirs(os.path.join(path, root))

    def run(self):
        for name, url in self.get_list():
            self.install_external_lib(name, url)


setup(name="pastedown",
      packages=["pastedown"],
      package_dir={"pastedown": "pastedown"},
      url="http://pastedown.lunant.net/",
      cmdclass={"download_libs": download_libs})


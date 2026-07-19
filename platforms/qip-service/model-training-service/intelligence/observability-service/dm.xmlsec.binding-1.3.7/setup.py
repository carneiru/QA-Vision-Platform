LXML_REQUIREMENT = "lxml>=3.0"

import sys, subprocess as commands
from os.path import abspath, dirname, join, exists
from os import environ

# see whether Cython is installed
try: import Cython
except ImportError: have_cython = False
else: have_cython = True

# to be extended when Cython is installed
cmdclass = {}

if have_cython:
  # we must work around `setuptools` to change `.pyx` into `.c` sources
  #  it does not find `Pyrex`
  sys.modules["Pyrex"] = Cython
  from Cython.Distutils import build_ext
  cmdclass["build_ext"] = build_ext

# installation requires "setuptools" (or equivalent) installed
from setuptools import setup, Extension

# we must extend our cflags once `lxml` is installed.
#  To this end, we override `Extension`
class Extension(Extension, object):
  lxml_extended = False

  def get_include_dirs(self):
    ids = self.__dict__["include_dirs"]
    if self.lxml_extended: return ids
    # ensure `lxml` headers come before ours
    #  this should make sure to use its headers rather than our old copy
    # ids.extend(get_lxml_include_dirs())
    ids[0:0] = get_lxml_include_dirs()
    self.lxml_extended = True
    return ids

  def set_include_dirs(self, ids): self.__dict__["include_dirs"] = ids

  include_dirs = property(get_include_dirs, set_include_dirs)

# determine macros, include dirs, libraries dirs and libraries required
#  for ourself, `libxml2` and `libxmlsec1`
define_macros = []
include_dirs  = ["src"]
library_dirs  = []
libraries     = []

def extract_cflags(cflags):
    global define_macros, include_dirs
    list = cflags.split(' ')
    for flag in list:
        if flag == '':
            continue
        flag = flag.replace("\\\"", "")
        if flag[:2] == "-I":
            if flag[2:] not in include_dirs:
                include_dirs.append(flag[2:])
        elif flag[:2] == "-D":
            t = tuple(flag[2:].split('='))
            if t not in define_macros:
                # fix provided by "tleppako@gmail.com"
                #  to let it work with 64 bit architectures
                #  see: http://lists.labs.libre-entreprise.org/pipermail/pyxmlsec-devel/2011-September/000082.html
                if len(t) == 1:
                    define_macros.append((t[0], "1"))
                else:
                    define_macros.append(t)
        else:
            print("Warning : cflag %s skipped" % flag)

def extract_libs(libs):
    global library_dirs, libraries
    list = libs.split(' ')
    for flag in list:
        if flag == '':
            continue
        if flag[:2] == "-l":
            if flag[2:] not in libraries:
                libraries.append(flag[2:])
        elif flag[:2] == "-L":
            if flag[2:] not in library_dirs:
                library_dirs.append(flag[2:])
        else:
            print("Warning : linker flag %s skipped" % flag)


libxml2_cflags = commands.getoutput('xml2-config --cflags')
if libxml2_cflags[:2] not in ["-I", "-D"]:
    sys.exit("Error : cannot get LibXML2 pre-processor and compiler flags; do you have the `libxml2` development package installed?")

libxml2_libs = commands.getoutput('xml2-config --libs')
if libxml2_libs[:2] not in ["-l", "-L"]:
    sys.exit("Error : cannot get LibXML2 linker flags; do you have the `libxml2` development package installed?")

crypto_engine = environ.get("XMLSEC_CRYPTO_ENGINE")
if crypto_engine is None:
  crypto_engine = commands.getoutput("xmlsec1-config --crypto")
  if not crypto_engine:
    sys.exit("Error: cannot get XMLSec1 crypto engine")
else:
  assert crypto_engine in ("openssl", "gnutls", "nss")
crypto_engine = " --crypto=" + crypto_engine
xmlsec1_cflags = commands.getoutput("xmlsec1-config --cflags" + crypto_engine)
if xmlsec1_cflags[:2] not in ["-I", "-D"]:
    sys.exit("Error: cannot get XMLSec1 pre-processor and compiler flags; do you have the `libxmlsec1` development package installed?")

xmlsec1_libs = commands.getoutput("xmlsec1-config --libs" + crypto_engine)
if xmlsec1_libs[:2] not in ["-l", "-L"]:
    sys.exit("Error : cannot get XMLSec1 linker flags; do you have the `libxmlsec1` development package installed?")

extract_cflags(libxml2_cflags)
extract_libs(libxml2_libs)

extract_cflags(xmlsec1_cflags)
extract_libs(xmlsec1_libs)


def get_lxml_include_dirs():
  lxml_home = environ.get("LXML_HOME")
  if lxml_home is None:
    # `LXML_HOME` not specified -- derive from installed `lxml`
    import lxml
    lxml_home = dirname(lxml.__file__)
  else:
    if not exists(lxml_home):
      sys.exit("The directory specified via envvar `LXML_HOME` does not exist")
    if exists(join(lxml_home, "src")): lxml_home = join(lxml_home, "src")
    if exists(join(lxml_home, "lxml")): lxml_home = join(lxml_home, "lxml")
  # check that it contains what is needed
  lxml_include = join(lxml_home, "includes")
  if not (exists(join(lxml_home, "etreepublic.pxd")) \
         or exists(join(lxml_include, "etreepublic.pxd"))):
    sys.exit("The lxml installation lacks the mandatory `etreepublic.pxd`. You may need to install `lxml` manually or set envvar `LXML_HOME` to an `lxml` installation with `etreepublic.pxd`")
  return [lxml_home, lxml_include]

# to work around a `buildout` bug (not honoring version pinning
#   for `setup_requires`), we try here to avoid `setup_requires`.
#   If envvar `LXML_HOME` is defined, we hope (i.e. no check) that
#   the `lxml` distribution it points to is compatible with the
#   `lxml` we will be finally using.
#   Otherwise, we let `pkg_resources` find and activate an
#   appropriate distribution.
SETUP_REQUIREMENTS = LXML_REQUIREMENT,

if environ.get("LXML_HOME"): SETUP_REQUIREMENTS = ()
else:
  try: from pkg_resources import require, DistributionNotFound, VersionConflict
  except ImportError: pass # should not happen
  else:
    try:
      for r in require(LXML_REQUIREMENT): r.activate()
    except VersionConflict:
      sys.exit("The available `lxml` version is incompatible with the version requirement: %s" % LXML_REQUIREMENT)
    except DistributionNotFound:
      pass # let setup install a version
    else: SETUP_REQUIREMENTS = ()



setupArgs = dict(
    include_package_data=True,
    setup_requires=SETUP_REQUIREMENTS, # see "http://mail.python.org/pipermail/distutils-sig/2006-October/006749.html" in case of problems
    install_requires=[
      'setuptools', # to make "buildout" happy
      LXML_REQUIREMENT,
    ] ,
    namespace_packages=['dm', 'dm.xmlsec',
                        ],
    zip_safe=False,
    entry_points = dict(
      ),
    test_suite='dm.xmlsec.binding.tests.testsuite',
    test_requires=['lxml'],
    )

cd = abspath(dirname(__file__))
pd = join(cd, 'dm', 'xmlsec', 'binding')

def pread(filename, base=pd): return open(join(base, filename)).read().rstrip()


setup(name='dm.xmlsec.binding',
      version=pread('VERSION.txt').split('\n')[0],
      description="Cython/lxml based binding for the XML security library -- for lxml 3.x",
      long_description=pread('README.txt'),
      classifiers=[
        #'Development Status :: 3 - Alpha',
        #'Development Status :: 4 - Beta',
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.4',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        "Operating System :: POSIX :: Linux",
        'Topic :: Utilities',
        ],
      author='Dieter Maurer',
      author_email='dieter@handshake.de',
      url='http://pypi.python.org/pypi/dm.xmlsec.binding',
      packages=['dm', 'dm.xmlsec', 'dm.xmlsec.binding'],
      license='BSD',
      keywords='encryption xml security digital signature cython lxml',
      ext_modules=[
        Extension(
          "dm.xmlsec.binding._xmlsec",
          ["src/_xmlsec.pyx"],
          define_macros=define_macros,
          include_dirs=include_dirs,
          library_dirs=library_dirs,
          libraries=libraries,
          depends=[
            "src/" + f for f in
            ("cxmlsec.pxd cxmlsec.h "
            "lxml.etree.h lxml-version.h lxml.etree_api.h").split()
             ]
                  ),
        ],
      cmdclass=cmdclass,
      **setupArgs
      )

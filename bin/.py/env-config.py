import sys
from ConfigParser import ConfigParser, NoSectionError, NoOptionError
from urlparse import urlparse

FILE = sys.argv[1]
SECTION = sys.argv[2]
OPTION = sys.argv[3]
FORMAT = sys.argv[4]

config = ConfigParser()
config.read(FILE)
try:
    res = config.get(SECTION, OPTION)
except (NoSectionError, NoOptionError):
    res = None

if res is None:
    print ''
elif FORMAT == 'str':
    print res
elif FORMAT == 'url':
    p = urlparse(res)
    print p.hostname if p.hostname is not None else ''
    print p.port if p.hostname is not None else ''
    print p.username if p.hostname is not None else ''
    print p.password if p.hostname is not None else ''
    print p.path.strip('/')

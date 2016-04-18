import sys
from urlparse import urlparse

if len(sys.argv) > 1:
    data = sys.argv[1]
else:
    data = sys.stdin.read()

p = urlparse(data)
print p.scheme if p.scheme is not None else ''
print p.hostname if p.hostname is not None else ''
print p.port if p.hostname is not None else ''
print p.username if p.hostname is not None else ''
print p.password if p.hostname is not None else ''
print p.path.strip('/')

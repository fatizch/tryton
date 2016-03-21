import sys
import os
from urlparse import urlparse
import redis

broker = sys.argv[2]
url = os.environ.get('TRYTOND_ASYNC_' + broker.upper())
url = urlparse(url)
host = url.hostname
port = url.port
db = url.path.strip('/')

client = redis.StrictRedis(host=host, port=port, db=db)
lua = sys.stdin.read()
query = client.register_script(lua)

print query(args=sys.argv[1:])

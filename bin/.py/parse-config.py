import sys
import ConfigParser
import StringIO

assert len(sys.argv) == 3, 'bad usage'

SECTION = sys.argv[1]
OPTION = sys.argv[2]

data = sys.stdin.read()

buf = StringIO.StringIO(data)
config = ConfigParser.ConfigParser()
config.readfp(buf)
print config.get(SECTION, OPTION)

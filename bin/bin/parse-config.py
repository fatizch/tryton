import os
import sys
from configparser import ConfigParser
from io import StringIO

assert len(sys.argv) == 3, 'bad usage'

SECTION = sys.argv[1]
OPTION = sys.argv[2]

data = sys.stdin.read()

buf = StringIO(data)
config = ConfigParser()
config.read_file(buf)


def update_environ():
    for key, value in os.environ.items():
        if not key.startswith('TRYTOND_'):
            continue
        try:
            section, option = key[len('TRYTOND_'):].lower().split('__', 1)
        except ValueError:
            continue
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)


update_environ()

print(config.get(SECTION, OPTION, fallback=''))

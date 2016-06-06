import sys
import json
import HTMLParser


def get_value(d, p):
    data = d
    for chunk in p.split('.'):
        data = data.get(chunk, {})
    return data


def print_value(v):
    if type(v) is dict:
        print(json.dumps(v))
    elif type(v) in (str, unicode):
        print(HTMLParser.HTMLParser().unescape(v))
    else:
        print(v)


data = sys.stdin.read()
obj = json.loads(data)

for p in sys.argv[1:]:
    v = get_value(obj, p)
    if type(v) is list:
        for e in v:
            print_value(e)
    else:
        print_value(v)

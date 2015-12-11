import sys
import json
import HTMLParser
h = HTMLParser.HTMLParser()

data = sys.stdin.read()
obj = json.loads(data)
print h.unescape(obj['value']['joke'])

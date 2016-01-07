import sys
import json
import HTMLParser
h = HTMLParser.HTMLParser()

data = sys.stdin.read()
try:
    entries = json.loads(data)['time_entries']
except:
    print 'Error occured !'
    sys.exit(1)
total = 0
for entry in entries:
    hours = entry['hours']
    project = h.unescape(entry['project']['name'])
    activity = h.unescape(entry['activity']['name'])
    issue = entry.get('issue', {'id': 0})['id']
    comment = h.unescape(entry.get('comments', ''))
    print u'{4}: {0: <10} {1: <30} {2: <5} {3}'.format(project, activity,
        issue, comment, hours)
    total += hours

print '\nYou have logged %s hours' % total

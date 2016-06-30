#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import sys
requests.packages.urllib3.disable_warnings()

REDMINE_URL = 'https://redmine.coopengo.com'

try:
    _, redmine_api_key, project_name, version_name = sys.argv
except ValueError:
    sys.stderr.write('''
Usage :
    burndown.py <redmine_api_key> <project_name> <version_name>

Example :
    burndown.py <valid_api_key> Coog sprint

''')
    sys.exit()

r = requests.get(REDMINE_URL + '/projects.json',
    auth=(redmine_api_key, ''), verify=False)
parsed = r.json()['projects']
possible_projects = []
if not parsed:
    sys.stderr.write('No projects found, check redmine api key !\n')
    sys.exit()

for project in parsed:
    if project['name'].encode('utf-8') == project_name:
        project_identifier = project['identifier']
        project_id = project['id']
        break
    else:
        possible_projects.append(project['name'].encode('utf-8'))
else:
    sys.stderr.write('Project %s not found\n\n' % project_name)
    sys.stderr.write('Possible projects :\n    ' +
        '\n    '.join(possible_projects))
    sys.stderr.write('\n')
    sys.exit()

r = requests.get(REDMINE_URL +
    '/projects/%s/versions.json' % project_identifier,
    auth=(redmine_api_key, ''), verify=False)
parsed = r.json()['versions']
possible_versions = []
for version in parsed:
    if version['name'].encode('utf-8') == version_name:
        fixed_version_id = version['id']
        break
    else:
        possible_versions.append(version['name'].encode('utf-8'))
else:
    sys.stderr.write('Version %s not found\n' % version_name)
    sys.stderr.write('Possible versions :\n    ' +
        '\n    '.join(possible_versions))
    sys.stderr.write('\n')
    sys.exit()

search_open_url = REDMINE_URL + '/issues.json?' \
    'offset=0&limit=5000&' \
    'project_id=%s&' % project_id + \
    'fixed_version_id=%i' % fixed_version_id
r_o = requests.get(search_open_url, auth=(redmine_api_key, ''), verify=False)

search_closed_url = REDMINE_URL + '/issues.json?' \
    'offset=0&limit=5000&' \
    'project_id=%s&' % project_id + \
    'fixed_version_id=%i&' % fixed_version_id + \
    'status_id=closed'
r_c = requests.get(search_closed_url, auth=(redmine_api_key, ''), verify=False)

all_ids = [x['id'] for x in r_o.json()['issues'] + r_c.json()['issues']]

total_estimated, total_done, number_done, number_todo, spent = 0, 0, 0, 0, 0
for issue_id in all_ids:
    issue_data = requests.get(REDMINE_URL + '/issues/%s.json' % issue_id,
            auth=(redmine_api_key, ''), verify=False)
    issue = issue_data.json()['issue']
    estimated = issue.get('estimated_hours', 0)
    if not estimated:
        print 'Ignoring issue %s, no estimated hours found' % issue['id']
        continue
    total_estimated += estimated
    spent += issue.get('spent_hours', 0)
    if issue['status']['id'] == 3:
        # 3 => Resolved
        total_done += estimated
        number_done += 1
    else:
        if issue.get('done_ratio', 0):
            total_done += estimated * issue['done_ratio'] / 100.0
        elif issue['status']['id'] == 7:
            # 7 => Review, assume 75% done
            total_done += estimated * 0.75
        elif issue.get('spent_hours', 0):
            # Assume spent_time accounts for max 50% of total estimated time
            total_done += min(issue['spent_hours'], estimated / 2.0)
        number_todo += 1

print '#' * 80
print ' '
print 'Number of Issue closed : %i' % number_done
print 'Number of Issue still opened : %i' % number_todo
print ' '
print 'Total estimated : %.2f' % total_estimated
print 'Total spent : %.2f' % spent
print 'Total done (estimation) : %.2f' % total_done
print 'Time remaining (estimation) : %.2f' % (total_estimated - total_done)
print ' '
print 'Good work, keep going !'
print ' '
print 'Remaining time is estimated as follow :'
print '  0 for closed issues'
print '  estimated time * (1 - done ratio) if done_ratio is set'
print '  estimated time * 0.75 for issues in review status'
print '  min(spent time, estimated time / 2) for other issues'

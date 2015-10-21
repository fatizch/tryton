#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import requests
import sys
from collections import defaultdict

REDMINE_URL = 'https://redmine.coopengo.com'

try:
    _, redmine_api_key, project_name, version_name = sys.argv
except ValueError:
    sys.stderr.write('''
Usage :
    bl.py <redmine_api_key> <project_name> <version_name>

Example :
    bl.py dwde0df0f2dd6invalid_api_key Coog sprint
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

search_url = REDMINE_URL + '/issues.json?' \
    'offset=0&limit=2000&' \
    'project_id=%s&' % project_id + \
    'fixed_version_id=%i&' % fixed_version_id + \
    'status_id=closed&' \
    'sort=priority,updated_on'

r = requests.get(search_url, auth=(redmine_api_key, ''), verify=False)
parsed = r.json()['issues']

features, bugs, params, scripts = defaultdict(list), defaultdict(list), [], []
for issue in parsed:
    issue['custom_fields'] = {x['id']: x.get('value', '').encode('utf-8')
        for x in issue['custom_fields']}
    issue['subject'] = issue['subject'].encode('utf-8')
    issue['updated_on'] = datetime.datetime.strptime(issue['updated_on'],
        '%Y-%m-%dT%H:%M:%SZ')
    if issue['tracker']['name'] == 'Feature':
        features[issue['priority']['name']].append(issue)
    else:
        bugs[issue['priority']['name']].append(issue)
    # Custom field 7 => Param
    if issue['custom_fields'].get(7, ''):
        params.append(issue)
    # Custom field 9 => Script
    if issue['custom_fields'].get(9, ''):
        scripts.append(issue)


def get_issue_id(issue):
    return '<a href="https://redmine.coopengo.com/issues/%i' % issue['id'] + \
        '">%i</a>' % issue['id']

print '<html>'
print '<head>'
print '<style>'
print '''
h1 {
    font-size: 120%;
}
table {
    border:#ccc 1px solid
    table-layout: fixed;
    width: 600px;
    border-width: 1px;
    border-color: #666666;
    border-collapse: collapse;
    border-spacing: 10px;
}
th {
    font-size: 90%;
    align: left;
    border-width: 1px;
    padding: 5px;
    border-style: solid;
    border-color: #666666;
    background-color: #dedede;
}
td {
    font-size: 80%;
    border-width: 1px;
    vertical-align: middle;
    padding: 2px;
    border-style: solid;
    border-color: #666666;
    background-color: #ffffff;
}
tr td:first-child {
    width: 70px;
}
tr td:last-child {
    width: 80px
}
'''
print '</style>'
print '</head>'
print '<body>'

count = 1
if features:
    print '<h1>%i. Features</h1>' % count
    count += 1
    for priority in ('Immediate', 'High', 'Normal', 'Low'):
        issues = features[priority]
        if not issues:
            continue
        print '<table>'
        print '<tr><th colspan="3">' + priority + ' (%s) :' % len(issues) + \
            '</th></tr>'
        for issue in issues:
            print '    <tr><td>' + get_issue_id(issue) + '</td><td>' + \
                issue['subject'] + '</td><td>%s</td></tr>' % (
                    issue['updated_on'])
        print '</table>'

if bugs:
    print '<h1>%i. Bugs</h1>' % count
    count += 1
    for priority in ('Immediate', 'High', 'Normal', 'Low'):
        issues = bugs[priority]
        if not issues:
            continue
        print '<table>'
        print '<tr><th colspan="3">' + priority + ' (%s) :' % len(issues) + \
            '</th></tr>'
        for issue in issues:
            print '    <tr><td>' + get_issue_id(issue) + '</td><td>' + \
                issue['subject'] + '</td><td>%s</td></tr>' % (
                    issue['updated_on'])
        print '</table>'


if params:
    print '<h1>%i. Params</h1>' % count
    count += 1
    print '<table>'
    print '    <tr><th>#</th><th>Subject</th><th width="200">Param</th></tr>'
    for issue in params:
        print '    <tr><td>' + get_issue_id(issue) + '</td><td>' + \
            issue['subject'] + '</td><td>' + \
            issue['custom_fields'][7] + '</td></tr>'
    print '</table>'


if scripts:
    print '<h1>%i. Scripts</h1>' % count
    count += 1
    print '<table>'
    print '    <tr><th>#</th><th>Subject</th><th width="200">Script</th></tr>'
    for issue in scripts:
        print '    <tr><td>' + get_issue_id(issue) + '</td><td>' + \
            issue['subject'] + '</td><td>' + \
            issue['custom_fields'][9] + '</td></tr>'
    print '</table>'
print '</body>'
print '</html>'

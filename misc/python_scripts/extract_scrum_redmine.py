#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import requests
import sys
import os
from relatorio.templates.opendocument import Template

REDMINE_URL = 'https://support.coopengo.com'

try:
    _, redmine_api_key, project_name, version_name, output_directory = sys.argv
except ValueError:
    try:
        _, redmine_api_key, project_name, version_name, output_directory = \
            sys.argv
    except ValueError:
        sys.stderr.write('''
Usage :
    extract_scrum_redmine.py <redmine_api_key> <project_name> <version_name> <output_directory>

Example :
    extract_scrum_redmine.py <valid_api_key> Root "Sprint 1.13.1" /tmp

    Will generate an odt file will all redmines request
    based on scrum_request_template.odt file".
''')
        sys.exit()

r = requests.get(REDMINE_URL + '/projects.json?limit=100',
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


def get_issues():
    offset = 0
    end = False
    while not end:
        search_url = REDMINE_URL + '/issues.json?' \
            'offset=%s&limit=100&' % offset + \
            'project_id=%s&' % project_id + \
            'fixed_version_id=%i&' % fixed_version_id + \
            'sort=priority,updated_on'

        r = requests.get(search_url, auth=(redmine_api_key, ''), verify=False)
        parsed = r.json()['issues']
        if not parsed:
            end = True
        else:
            for issue in parsed:
                yield issue
            offset += 100

resquests_details = []
for issue in get_issues():
    issue['updated_on'] = datetime.datetime.strptime(issue['updated_on'],
        '%Y-%m-%dT%H:%M:%SZ')
    resquests_details.append(issue)

basic = Template(source='', filepath='scrum_request_template.odt')
basic_generated = basic.generate(requests=resquests_details).render()
output_file = os.path.join(output_directory, 'scrum_request.odt')
file(output_file, 'wb').write(basic_generated.getvalue())

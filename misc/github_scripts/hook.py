from flask import Flask, request
import json
import requests
import traceback

GITHUB_TOKEN = 'github api token, requires read / write access to commits'

REDMINE_URL = 'https://redmine.coopengo.com'
REDMINE_TOKEN = 'redmine api token'
REDMINE_BUG_ID = 1
REDMINE_FEATURE_ID = 2
REDMINE_TASK_ID = 3
ALLOWED_PROJECTS = {
    'coopengo/coog': [
        1,   # Coog
        29,  # Coog-Tech
        31,  # Maintenance Coog
        37,  # Code rewriting
        ],
    }

DESCRIPTIONS = {
    'commit_title': 'dev-github-hooks#testingcommit_title',
    'commit_body': 'dev-github-hooks#testingcommit_body',
    'labels': 'dev-github-hooks#testinglabels',
    'contents': 'dev-github-hooks#testingcontents',
    }


app = Flask(__name__)


@app.route('/', methods=['POST'])
def foo():
    try:
        data = json.loads(request.data)
        if 'pull_request' not in data:
            return
        # Title modification :
        #    data['action'] == 'edited'
        #    'title' in data['changes']

        # Body modification :
        #    data['action'] == 'edited'
        #    'body' in data['changes']

        # New PR :
        #    data['action'] == 'opened'

        # Label added :
        #    data['action'] == 'labeled'
        #    data['label']['name'] => 'bug'

        # Label removed :
        #    data['action'] == 'unlabeled'
        #    data['label']['name'] => 'bug'

        # Get all labels :
        #   requests.get(data['pull_request']['_links']['issue'] + '/labels' +
        #       '?access_GITHUB_TOKEN=' + github_token)

        # Pull request updated :
        #   data['action'] == 'synchronize'

        # Pull request target :
        #   data['pull_request']['base']['repo']['full_name'] ==
        #       'coopengo/coog'

        body = data['pull_request']['body']
        if '##NOCHECK##' in body:
            messages = [
                ('success', x, 'FORCED !')
                for x in ('commit_title', 'commit_body', 'labels', 'contents')]
            return
        messages = []
        print 'Received status %s' % data['action']
        if data.get('action', '') in 'edited' and ('title' in data['changes']
                or 'body' in data['changes']):
            check_title(data, messages)
            check_body(data, messages)
            check_labels(data, messages)
            check_contents(data, messages)
        elif data.get('action', '') in ('labeled', 'unlabeled'):
            check_labels(data, messages)
            check_contents(data, messages)
        elif data.get('action', '') == 'opened':
            check_title(data, messages)
            check_body(data, messages)
            check_labels(data, messages)
            check_contents(data, messages)
        elif data.get('action', '') == 'synchronize':
            check_contents(data, messages)
        print 'Done'
    except:
        messages = [
            ('error', x, 'CRASH !')
            for x in ('commit_title', 'commit_body', 'labels', 'contents')]
        traceback.print_exc()
    finally:
        if 'pull_request' in data:
            for state, context, description in messages:
                payload = {
                    'state': state,
                    'context': 'testing/' + context,
                    'target_url': 'https://github.com/coopengo/coog/wiki/' +
                    DESCRIPTIONS[context],
                    'description': description,
                    }
                url = (data['repository']['statuses_url'][:-5] +
                    data['pull_request']['head']['sha'] + '?access_token=' +
                    GITHUB_TOKEN)
                requests.post(url, data=json.dumps(payload))
        return 'OK'


def get_labels(data):
    if 'labels' in data:
        return data['labels']
    labels = requests.get(
        data['pull_request']['_links']['issue']['href'] +
        '/labels' + '?access_token=' + GITHUB_TOKEN).json()
    data['labels'] = [x['name'] for x in labels]
    return data['labels']


def get_redmine_reference(data):
    if 'redmine_issue' in data:
        return data['redmine_issue']
    data['redmine_issue'] = None
    last_line = data['pull_request']['body'].split('\n')[-1]
    if not last_line.startswith('Fix #'):
        return
    try:
        data['redmine_issue'] = last_line[5:]
        return data['redmine_issue']
    except:
        return


def get_redmine_data(data):
    if 'redmine_data' in data:
        return data['redmine_data']
    number = get_redmine_reference(data)
    data['redmine_data'] = requests.get(REDMINE_URL + '/issues/' + number +
            '.json', auth=(REDMINE_TOKEN, ''), verify=False).json()['issue']
    return data['redmine_data']


def get_pull_request_files(data):
    if 'pr_files' in data:
        return data['pr_files']
    data['pr_files'] = requests.get(
            data['pull_request']['_links']['self']['href'] + '/files' +
            '?access_token=' + GITHUB_TOKEN).json()
    return data['pr_files']


def check_title(data, messages):
    title = data['pull_request']['title']
    if ': ' not in title:
        messages.append(('failure', 'commit_title',
            'Expected "<module>: <short title>"'))
    elif title.endswith('...'):
        messages.append(('failure', 'commit_title',
            'Title cannot end with "..."'))
    else:
        messages.append(('success', 'commit_title', ''))


def check_body(data, messages):
    body = data['pull_request']['body']
    if body == '':
        messages.append(('failure', 'commit_body', 'Empty body'))
        return
    if not get_redmine_reference(data):
        messages.append(('failure', 'commit_body',
        'Missing or malformed redmine reference'))
        return
    lines = body.split('\n')
    if len(lines) > 1:
        if lines[-2] != '':
            messages.append(('failure', 'commit_body',
                'Missing empty line before redmine reference'))
            return
    messages.append(('success', 'commit_body', ''))


def check_labels(data, messages):
    labels = get_labels(data)
    if 'bug' not in labels and 'enhancement' not in labels:
        messages.append(('failure', 'labels',
            'No bug or enhancement labels found'))
        return
    if 'bug' in labels and 'enhancement' in labels:
        messages.append(('failure', 'labels',
            'Cannot have both "bug" and "enhancement" label'))
        return
    redmine_number = get_redmine_reference(data)
    if not redmine_number:
        messages.append(('failure', 'labels', 'Cannot find redmine issue'))
        return
    try:
        redmine_data = get_redmine_data(data)
    except:
        traceback.print_exc()
        messages.append(('error', 'labels', 'Error accessing redmine'))
        return
    if ('bug' in labels and
            redmine_data['tracker']['id'] != REDMINE_BUG_ID):
        messages.append(('failure', 'labels', 'Issue %s is not a bug !'
                % redmine_number))
        return
    if ('enhancement' in labels and
            redmine_data['tracker']['id'] not in (REDMINE_FEATURE_ID,
                REDMINE_TASK_ID)):
        messages.append(('failure', 'labels', 'Issue %s is not a feature !'
                % redmine_number))
        return
    if redmine_data['project']['id'] not in ALLOWED_PROJECTS[
            data['pull_request']['base']['repo']['full_name']]:
        messages.append(('failure', 'labels', 'Bad project for issue %s'
                % redmine_number))
        return
    messages.append(('success', 'labels', ''))


def check_contents(data, messages):
    files = get_pull_request_files(data)
    if not files:
        messages.append(('failure', 'contents', 'Empty pull request'))
        return
    file_paths = [x['filename'] for x in files]
    if 'enhancement' in get_labels(data):
        if not any(['features.rst' in x for x in file_paths]):
            messages.append(('failure', 'contents', 'Missing doc for feature'))
            return
        if not any(['features_log' in x for x in file_paths]):
            messages.append(('failure', 'contents', 'Missing log entry for '
                    'feature'))
            return
    messages.append(('success', 'contents', ''))


if __name__ == '__main__':
    app.run()

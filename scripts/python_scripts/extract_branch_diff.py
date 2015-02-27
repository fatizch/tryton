#!/usr/bin/env python
import sys
import os
import subprocess
import requests

URL = 'https://redmine.coopengo.com/issues/'
CUR_PATH = os.getcwd()


def get_ancestor(base, dest):
    # Returns common ancestor of base and dest revision
    proc = subprocess.Popen('hg log -r "ancestor(%s,%s)" ' % (base, dest) +
        '--template="{node}"', stdout=subprocess.PIPE, shell=True)
    ancestor, err = proc.communicate()
    if err:
        raise Exception(err)
    return ancestor


def get_diff_issues(ancestor, target):
    commands = [
        # Extract all changesets from ancestor on branch target
        'hg log -r %s::%s --style=default' % (ancestor, target),
        # Filter the lines on which a #1234 flag appears
        'grep "#[0-9]\+"',
        # New line on all groups
        'sed -e "s/#\([0-9]\\+\)/\\n#\\1/g"',
        # Only keep good lines
        'grep "#[0-9]\+"',
        # Clean up
        'sed -e "s/#\([0-9]\+\).*$/\\1/"',
        ]
    proc = subprocess.Popen(' | '.join(commands), stdout=subprocess.PIPE,
        shell=True)
    issue_numbers, err = proc.communicate()
    if err:
        raise Exception(err)
    issue_numbers = set([int(x) for x in issue_numbers.split('\n') if x])
    return issue_numbers


def extract_redmine_issues(issue_numbers, api_key):
    output = [';'.join(['Issue Number', 'Project', 'Tracker', 'Priority',
                'Status', 'Author', 'Creation Date', 'Due Date', 'Subject'])]
    try:
        for issue in issue_numbers:
            r = requests.get(URL + '%s.json' % issue, auth=(api_key, ''),
                verify=False)
            parsed = r.json()['issue']
            subject = parsed['subject']
            author = parsed['author']['name']
            creation_date = parsed['created_on'][:10]
            project = parsed['project']['name']
            status = parsed['status']['name']
            priority = parsed['priority']['name']
            tracker = parsed['tracker']['name']
            due_date = parsed.get('due_date', '')
            output.append(';'.join([str(issue), project, tracker, priority,
                        status, author, creation_date, due_date, subject]))
    except:
        print 'Error contacting the redmine server %s' % URL
        sys.exit(0)
    print '\n'.join(output)


if __name__ == '__main__':
    try:
        _, api_key_file, repo_path, base_branch, dest_branch = sys.argv
    except:
        print 'Usage : extract_branch_diff.py api_key_file ' \
            '/path/to/repo default prod'
        print ''
        print '    api_key_file must be a path to a readable file with a valid'
        print '        redmine api key'
        print '    default / prod must be branch names, tags, or changesets'
        print '    The most up-to-date entry must be first'
        sys.exit(0)
    os.chdir(repo_path)
    try:
        try:
            with open(api_key_file, 'r') as api_file:
                api_key = api_file.readlines()[0].strip()
        except:
            print 'Could not get an api key from file %s' % api_key_file
            sys.exit(0)
        ancestor = get_ancestor(base_branch, dest_branch)
        base_issues = get_diff_issues(ancestor, base_branch)
        dest_issues = get_diff_issues(ancestor, dest_branch)
        diff = base_issues - dest_issues
        if not diff:
            print 'No differential issues'
            sys.exit(0)
        extract_redmine_issues(sorted(list(diff)), api_key)
    finally:
        os.chdir(CUR_PATH)
    sys.exit(0)

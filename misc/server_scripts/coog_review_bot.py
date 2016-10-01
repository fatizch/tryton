#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script ...
- review python file uploaded to rietveld for pep8 and others rules that
  apply to coog code.
- change related redmine issues to 'review' (use the "fix #XXX" keyword in your
  review title)
- close issues if called with the '-c' switch

Usage:
For reviewing purpose, it should be launched by a cron job regularly.
For closing purpose, you need to add the following in your repo .hg/hgrc :
     [hooks]
     incoming = hg log -vr $HG_NODE | python /path/to/coog_review_bot.py -c

Configuration:
You  need to create a coog.conf file in the home directory
of the user lauching the script
The rietveld.conf file should contain the following:

[credentials]
email = youremail
password = yourpassword
redmine_api_key = admin_api_key

[repositories]
repositories = /path/to/your/repos/directories
"""

import re
import os.path
import tempfile
import urlparse
import shutil
import json
import anydbm
import ConfigParser
import sys
import fileinput
import argparse

import pep8
import flake8.engine
import requests
import mercurial
from mercurial import ui, hg
from mercurial import commands
import hgreview

from datetime import date, timedelta

CONF_FILE = '~/coog.conf'
TITLE_FORMAT = re.compile('^([A-Za-z_][\w\.-]+)+ ?:')
CODEREVIEW_URL = 'http://rietveld.coopengo.com'
REDMINE_URL = 'https://redmine.coopengo.com'
ISSUE_REGEXP = re.compile('(rietveld.coopengo.com/)([0-9]+)')


def get_session(url, email, password):
    session = requests.Session()
    r = session.post('https://www.google.com/accounts/ClientLogin',
        data={
            'Email': email,
            'Passwd': password,
            'service': 'ah',
            'source': 'rietveld-codereview-upload',
            'accountType': 'GOOGLE',
            })
    if r.status_code != 200:
        return None
    r_dict = dict(x.split('=') for x in r.text.split('\n') if x)

    cookie_url = url + '/'.join(['', '_ah', 'login'])
    session.get(cookie_url, params={
            'auth': r_dict['Auth'],
            'action': 'Login',
            'continue': CODEREVIEW_URL,
            })
    return session


class RietveldStyle(flake8.engine.StyleGuide):

    def __init__(self, basename, *args, **kwargs):
        self.basename = basename
        super(RietveldStyle, self).__init__()
        self.options.max_complexity = -1  # do not check code complexity
        self.options.builtins = []  # use the default builtins
        self.options.ignore = (
            'E122',  # continuation line missing indentation or outdented
            'E123',  # closing bracket does not match indentation of opening
                     # bracket’s line
            'E124',  # closing bracket does not match visual indentation
            'E126',  # continuation line over-indented for hanging indent
            'E128',  # continuation line under-indented for visual indent
            'E711',  # comparison to None should be ‘if cond is None:’
            'F403',  # ‘from module import *’ used;
                     #  unable to detect undefined names
            )

        # jeremy : quick fix , not sure about this:
        self.options.doctests = None

    def init_report(self, reporter=None):
        self.options.report = RietveldReport(self.basename, self.options)
        return self.options.report


class RietveldReport(pep8.BaseReport):

    def __init__(self, basename, options):
        super(RietveldReport, self).__init__(options)
        self.basename_prefix = len(basename)
        self.errors = []

    def error(self, line_number, offset, text, check):
        code = super(RietveldReport, self).error(line_number, offset, text,
            check)
        if not code:
            return
        self.errors.append({
                'text': text,
                'lineno': line_number,
                'filename': self.filename[self.basename_prefix + 1:],
                })


def get_style(repository):
    # This is the way to initialize the pyflake checker
    parser, option_hooks = flake8.engine.get_parser()
    styleguide = RietveldStyle(repository, parser=parser)
    options = styleguide.options
    for hook in option_hooks:
        hook(options)
    return styleguide


class ReviewSession:

    def __init__(self, url, email, password):
        self.url = url
        self.session = get_session(url, email, password)
        self.xsrf_token = self.get_xsrf_token()

    def get_xsrf_token(self):
        response = self.session.get(urlparse.urljoin(self.url, 'xsrf_token'),
            headers={
                'X-Requesting-XSRF-Token': 1,
                })
        if response.status_code != 200:
            return None
        else:
            return response.text

    def get(self, *args, **kwargs):
        return self.session.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        if 'data' not in kwargs:
            kwargs['data'] = {'xsrf_token': self.xsrf_token}
        else:
            kwargs['data']['xsrf_token'] = self.xsrf_token
        return self.session.post(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.session, name)


def install_repository(repo_url, branch=None):
    repo_dir = tempfile.mkdtemp(prefix='reviewbot-')
    my_ui = ui.ui()
    commands.clone(my_ui, repo_url.encode('ascii'), repo_dir,  # hg wants a str
        branch=branch)
    return repo_dir


def patch_repository(repo_dir, issue_id, email, password):
    my_ui = ui.ui()
    my_ui.setconfig('review', 'server', CODEREVIEW_URL)
    my_ui.setconfig('review', 'username', email)
    my_ui.setconfig('review', 'password', password)
    repo = hg.repository(my_ui, repo_dir)
    hgreview.review(my_ui, repo, clean=False, fetch=True, issue=issue_id,
        rev=None, id=None, url=None)
    return issue_id


def has_update(rietveld_db_path, entry_id, patchset):
    db = anydbm.open(rietveld_db_path, 'c')
    if entry_id not in db:
        update_p = True
    else:
        update_p = db[entry_id] != str(patchset)
    db.close()
    return update_p


def set_update(rietveld_db_path, entry_id, patchset):
    db = anydbm.open(rietveld_db_path, 'c')
    new_entry = entry_id not in db
    db[entry_id] = str(patchset)
    db.close()
    return new_entry


def send_comments(session, issue_id, patchset, comments, repo_dir):
    patchset_url = urlparse.urljoin(CODEREVIEW_URL,
        '/'.join(['api', str(issue_id), str(patchset)]))
    patchset_info = session.get(patchset_url)
    if patchset_info.status_code != 200:
        return
    patchset_info = json.loads(patchset_info.text)
    commented = False
    for comment in comments:
        if comment['filename'] not in patchset_info['files']:
            continue
        commented = True
        comment['snapshot'] = 'new'
        comment['side'] = 'b'
        comment['issue'] = issue_id
        comment['patchset'] = patchset
        comment['patch'] = patchset_info['files'][comment['filename']]['id']
        session.post(CODEREVIEW_URL + '/inline_draft', data=comment)
    res = ''
    warnings = []
    for file_name in patchset_info['files']:
        if not file_name.endswith('.py'):
            continue
        try:
            with open(repo_dir + '/' + file_name) as f:
                warns = check_on_delete(f.readlines())
                for w in warns:
                    w['filename'] = file_name
                    w['snapshot'] = 'new'
                    w['side'] = 'b'
                    w['issue'] = issue_id
                    w['patchset'] = patchset
                    w['patch'] = patchset_info['files'][w['filename']]['id']
        except Exception as e:
            print e
    if not commented:
        res = 'flake8 OK'
    if 'CHANGELOG' not in ''.join(patchset_info['files']):
        warnings.append('no CHANGELOG')
    if warnings:
        return res + '\nWarnings:\n\t' + ',\n\t'.join(warnings)
    else:
        return res


def check_on_delete(lines):
    if 'fields.Many2One' not in ''.join(lines):
        return []
    warnings = []
    for i, line in enumerate(lines):
        if ('fields.Many2One' not in line or
                ' = ' not in line or
                'fields.Function' in lines[i - 1] or
                'fields.Function' in line):
            continue
        if 'ondelete' in line:
            continue
        if i == (len(lines) - 1):
            if 'ondelete' not in line:
                warnings.append({'lineno': i + 1, 'text': 'ondelete not set'})
        else:
            got_ondelete = False
            for line in lines[i + 1:]:
                if 'fields.' in line and not got_ondelete:
                    warnings.append({'lineno': i + 1,
                            'text': 'ondelete not set'})
                    break
                else:
                    if 'ondelete' in line:
                        got_ondelete = True
    return warnings


def finalize_comments(session, issue_info, message):
    url = (CODEREVIEW_URL
        + '/'.join(['', str(issue_info['issue']), 'publish']))
    session.post(url, data={
            'message': message,
            'send_mail': False,
            'reviewers': ','.join(issue_info['reviewers']),
            'cc': issue_info['cc'],
            })


def get_rm_issue_next_version(issue_url, force=False):
    r = requests.get(issue_url, auth=(redmine_api_key, ''), verify=False)
    issue_json = json.loads(r.text)['issue']
    if force or 'fixed_version' not in issue_json:
        url_proj = '%s/projects/%d/versions.json' % (REDMINE_URL,
            issue_json['project']['id'])
        r = requests.get(url_proj, auth=(redmine_api_key, ''),
            headers={'content-type': 'application/json'}, verify=False)
        versions = json.loads(r.text)['versions']
        for v in versions:
            if 'custom_fields' in v:
                for cf in v['custom_fields']:
                    if cf['id'] == 8 and 'value' in cf and \
                            int(cf['value']):
                        return v['id']


def extract_rm_issues_urls(description):
    pattern = r"(close|closes|fix|fixes) #([0-9]+)"
    matches = re.findall(re.compile(pattern, re.IGNORECASE), description)
    redmine_issue_url_root = '%s/issues/' % REDMINE_URL
    return ['%s/%s.json' % (redmine_issue_url_root, m[1]) for m in matches]


def put_rm_issue(url, payload, redmine_api_key):
    requests.put(url, auth=(redmine_api_key, ''),
        data=json.dumps({'issue': payload}),
        verify=False,
        headers={'content-type': 'application/json'})


def update_rm_issue_on_close(issue_id, description, user, redmine_api_key):
    for url in extract_rm_issues_urls(description):
        next_version = get_rm_issue_next_version(url, force=True)
        if next_version:
            issue_changes = {'fixed_version_id': next_version}
            put_rm_issue(url, issue_changes, redmine_api_key)


def update_rm_issue_on_review(issue_id, description, user, patchset,
        redmine_api_key):
    rm_issue_status = {'status_review': 7}
    rm_custom_fields = {'review_cf': 2}
    notes = 'Review updated at http://rietveld.coopengo.com/%s/#ps%s by %s' % \
        (issue_id, patchset, user)
    for url in extract_rm_issues_urls(description):
        next_version = get_rm_issue_next_version(url)
        issue_changes = {
                'status_id': rm_issue_status['status_review'],
                'notes': notes,
                'custom_fields': [
                    {'id': rm_custom_fields['review_cf'], 'value': issue_id},
                ]}
        if next_version:
            issue_changes['fixed_version_id'] = next_version
        put_rm_issue(url, issue_changes, redmine_api_key)


def check_style(session, issue_url, repo_path, email, password):
    match = TITLE_FORMAT.match(issue_info['subject'])
    if not match:
        finalize_comments(session, issue_info,
            "Review's title does not follow the convention: '%s'"
            % TITLE_FORMAT.pattern)
        return
    prefix = match.groups()[0]
    branch = None
    if prefix in ('tryton', 'trytond'):
        repository_url = repo_path + prefix
        if prefix == 'trytond':
            branch = ['dev']
        else:
            branch = ['coopengo']
    else:
        repository_url = repo_path + 'coog'
        branch = ['coog']

    repo_dir = install_repository(repository_url, branch)
    try:
        patch_repository(repo_dir, issue_id, email, password)
    except mercurial.error.Abort:
        shutil.rmtree(repo_dir)
        finalize_comments(session, issue_info,
            'patch is not applicable on trunk')
        return
    style_guide = get_style(repo_dir)
    report = style_guide.check_files([repo_dir])
    final_message = send_comments(session, issue_id,
        issue_info['patchsets'][-1], report.errors, repo_dir)
    finalize_comments(session, issue_info, final_message)
    shutil.rmtree(repo_dir)


def fetch_issues(url, session):
    text_result = session.get(url).text
    dic_result = json.loads(text_result)
    issues_urls = []
    for item in dic_result['results']:
        if not item['closed']:
            issues_urls.append(CODEREVIEW_URL + '/' + str(item['issue']))
    return issues_urls


def close_issue(session, issue_number):
    url = (session.url
        + '/'.join(['', str(issue_number), 'close']))
    r = session.post(url)
    print r.text


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Rietveld bot')
    parser.add_argument('--close', '-c', help='Close issues found in stdin',
        action='store_true')
    arguments = parser.parse_args()

    config = ConfigParser.ConfigParser()
    try:
        with open(os.path.expanduser(CONF_FILE), 'r') as fconf:
                config.readfp(fconf)
    except Exception as e:
        print "Error while trying to read from %s file: %s" % (CONF_FILE, e)
        sys.exit(1)

    email = config.get('credentials', 'email')
    password = config.get('credentials', 'password')
    redmine_api_key = config.get('credentials', 'redmine_api_key')
    repo_path = config.get('paths', 'repositories_url')
    rietveld_db_path = config.get('paths', 'rietveld_db')
    session = ReviewSession(CODEREVIEW_URL, email, password)
    most_ancient = date.today() - timedelta(days=7)
    issues_urls = fetch_issues(CODEREVIEW_URL +
        '/search?modified_after=' + str(most_ancient) +
        '&closed=0&format=json', session)

    if arguments.close:
        for line in fileinput.input('-'):
            mymatch = ISSUE_REGEXP.search(line)
            if mymatch:
                close_issue(session, mymatch.groups()[1])
    for issue_url in issues_urls:
        issue_id = urlparse.urlparse(issue_url).path.split('/')[1]
        issue_info = session.get('%s%s' % (CODEREVIEW_URL,
            '/'.join(['', 'api', str(issue_id)])))
        if issue_info.status_code != 200:
            continue
        issue_info = json.loads(issue_info.text)
        # Test only last patchset has changed
        patchset = issue_info['patchsets'][-1]
        if not has_update(rietveld_db_path, issue_id, patchset):
            continue
        email = issue_info["owner_email"].split('@')[0]
        if arguments.close:
            update_rm_issue_on_close(issue_info['issue'],
                issue_info['subject'], email, redmine_api_key)
        else:
            set_update(rietveld_db_path, issue_id, patchset)
            check_style(session, issue_url, repo_path, email, password)
            update_rm_issue_on_review(issue_info['issue'],
                issue_info['subject'], email, patchset, redmine_api_key)

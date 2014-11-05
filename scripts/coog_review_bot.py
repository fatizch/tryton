#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script will review the pep8 for python file uploaded to rietveld.
It shoud be launched by a cron job regularly.

You  need to create a rietveld.conf file in the home directory
of the user lauching the script
The rietveld.conf file should contain the following:

[credentials]
email = youremail
password = yourpassword

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
import datetime
import ConfigParser
import sys

import pep8
import flake8.engine
import requests
import mercurial
from mercurial import ui, hg
from mercurial import commands
import hgreview

TITLE_FORMAT = re.compile('^([A-Za-z_][\w\.-]+)+ ?:')
CODEREVIEW_URL = 'http://rietveld.coopengo.com'
DB_PATH = os.path.expanduser('~/review_bot/.reviewbot.db')  # Adapt to config


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


class RietveltStyle(flake8.engine.StyleGuide):

    def __init__(self, basename, *args, **kwargs):
        self.basename = basename
        super(RietveltStyle, self).__init__()
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
        self.options.report = RietveltReport(self.basename, self.options)
        return self.options.report


class RietveltReport(pep8.BaseReport):

    def __init__(self, basename, options):
        super(RietveltReport, self).__init__(options)
        self.basename_prefix = len(basename)
        self.errors = []

    def error(self, line_number, offset, text, check):
        code = super(RietveltReport, self).error(line_number, offset, text,
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
    styleguide = RietveltStyle(repository, parser=parser)
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


def has_update(entry_id, patchset):
    db = anydbm.open(DB_PATH, 'c')
    if entry_id not in db:
        update_p = True
    else:
        update_p = db[entry_id] != str(patchset)
    db.close()
    return update_p


def set_update(entry_id, patchset):
    db = anydbm.open(DB_PATH, 'c')
    db[entry_id] = str(patchset)
    db.close()


def send_comments(session, issue_id, patchset, comments):
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
    return commented


def finalize_comments(session, issue_info, message):
    url = (CODEREVIEW_URL
        + '/'.join(['', str(issue_info['issue']), 'publish']))
    session.post(url, data={
            'message': message,
            'send_mail': False,
            'reviewers': ','.join(issue_info['reviewers']),
            'cc': issue_info['cc'],
            })


def process_issue(session, issue_url, path_to_repo, email, password):
    issue_id = urlparse.urlparse(issue_url).path.split('/')[1]
    issue_info = session.get(CODEREVIEW_URL
        + '/'.join(['', 'api', str(issue_id)]))
    if issue_info.status_code != 200:
        return
    else:
        issue_info = json.loads(issue_info.text)

    # Test only last patchset has changed
    patchset = issue_info['patchsets'][-1]
    if not has_update(issue_id, patchset):
        return
    set_update(issue_id, patchset)

    match = TITLE_FORMAT.match(issue_info['subject'])
    if not match:
        finalize_comments(session, issue_info,
            "Review's title does not follow the convention: '%s'"
            % TITLE_FORMAT.pattern)
        return
    prefix = match.groups()[0]
    branch = None
    if prefix in ('tryton', 'trytond'):
        repository_url = path_to_repo + prefix
        if prefix == 'trytond':
            branch = ['dev']
        else:
            branch = ['coopengo']
    else:
        repository_url = path_to_repo + 'coopbusiness'
        branch = ['default']

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
    if send_comments(session, issue_id, issue_info['patchsets'][-1],
            report.errors):
        finalize_comments(session, issue_info, '')
    else:
        finalize_comments(session, issue_info, 'flake8 OK')
    shutil.rmtree(repo_dir)


def fetch_issues(url, session):
    text_result = session.get(url).text
    dic_result = json.loads(text_result)
    issues_urls = []
    for item in dic_result['results']:
        if not item['closed']:
            issues_urls.append(CODEREVIEW_URL + '/' + str(item['issue']))
    return issues_urls


if __name__ == '__main__':

    config = ConfigParser.ConfigParser()
    try:
        with open(os.path.expanduser('~/rietveld.conf'), 'r') as fconf:
                config.readfp(fconf)
    except:
        print "Error while trying to read from rietveld.conf file"
        sys.exit(1)

    email = config.get('credentials', 'email')
    password = config.get('credentials', 'password')
    path_to_repo = config.get('repositories', 'repositories_url')

    session = ReviewSession(CODEREVIEW_URL, email, password)
    most_ancient = datetime.date.today() - datetime.timedelta(days=7)

    issues_urls = fetch_issues(CODEREVIEW_URL +
        '/search?modified_after=' + str(most_ancient) +
        '&closed=0&format=json', session)

    for issue_url in issues_urls:
        process_issue(session, issue_url, path_to_repo, email, password)

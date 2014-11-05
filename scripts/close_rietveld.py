#!/usr/bin/env python

"""
This script will close the rietveld issue mentionned in the comment
of a commit when a commit is incoming to the repo.
The full url to the issue should be provided.

To make this script work, you need to add the following
in the .hg/hgrc file of the repo:

    [hooks]
    incoming = hg log -vr $HG_NODE | python /path/to/close_rietveld.py

You also need to create a rietveld.conf file in the home directory
of the user lauching the script
The rietveld.conf file should contain the following:

    [credentials]
    email = youremail
    password = yourpassword

The credentials above should be for a google account.
This script would probably not work if the double authentication
is activated for the email account mentionned in the credentials section.

"""


import fileinput
import requests
import urlparse
import re
import ConfigParser
import os
import sys

ISSUE_REGEXP = re.compile('(rietveld.coopengo.com/)([0-9]+)')
CODEREVIEW_URL = 'http://rietveld.coopengo.com'


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
            'continue': url,
            })
    return session


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


def close_issue(session, issue_number):
    url = (session.url
        + '/'.join(['', str(issue_number), 'close']))
    r = session.post(url)
    print r.text

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

    session = ReviewSession(CODEREVIEW_URL, email,
        password)

    for line in fileinput.input():
        mymatch = ISSUE_REGEXP.search(line)
        if mymatch:
            close_issue(session, mymatch.groups()[1])

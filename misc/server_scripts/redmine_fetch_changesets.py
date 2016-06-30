#!/usr/bin/env python
import ConfigParser
import requests
import warnings
import sys
import os

"""
    Script to call via a repo changegroup hook to force redmine updates.
"""

CONF_FILE = '~/coog.conf'
PROJ_ID = 'coog'

if __name__ == '__main__':
    config = ConfigParser.ConfigParser()
    try:
        with open(os.path.expanduser(CONF_FILE), 'r') as fconf:
                config.readfp(fconf)
    except:
        print "Error while trying to read from %s file" % CONF_FILE
        sys.exit(1)

    redmine_ws_key = config.get('credentials', 'redmine_ws_key')

    warnings.filterwarnings("ignore")
    print 'Fetching hg changesets in Redmine...'
    url = 'https://redmine.coopengo.com/sys/fetch_changesets?id=%s&key=%s' % \
        (PROJ_ID, redmine_ws_key)
    requests.get(url, verify=False)

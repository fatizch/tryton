#!/usr/bin/python

"""
This script will launch the coog tests and mail the results
to a list of recipients. You need to create an 'auto_tests.conf' file
in the home directory of the user launching the script.
This auto_tests.conf file must contain the following:

[tests]
path_to_running_file = /path/to/a/directory
path_to_workspace = /path/to/tryton-workspace
repo_url = https://url.to.repo/

[mailing]
recipients = riri@fifi.com,fifi@fifi.com,loulou@fifi.com
email = someone@your_provider.com
password = the_password
smtp_server = smtp.your_provider.com
smtp_port = 587 (it should match your stmp server's port)

This script can for example be launched by a mercurical hook
in the coopbusiness repository, and/or by a cron job.

If you want to launch the tests when changes are pushed to your repo,
you can add a hook on the repos.  and add a cronjob to regularly update
your test repo from a central repository.

This script uses an empty "running" file to record the state of the tests.
If the tests are running, the "running file" contains 1, else
it contains 0. This "running" file can then be used to easily control
the lauch of the script in an automated environnement, for example
to prevent the launches of several simultaneous test sessions.

If you use a mercurial hook in your repo to launch the tests
as suggested above, you can use a simple bash script, called by cron,
that will check the state of the "running" file,
and only update the repo if the running file contains '0'.

"""

import os
import subprocess
import smtplib
import ConfigParser
import sys

from email.mime.text import MIMEText
from tendo import singleton

me = singleton.SingleInstance()

config = ConfigParser.ConfigParser()


try:
    with open(os.path.expanduser('~/auto_tests.conf')) as fconf:
        config.readfp(fconf)
except:
    print "Error while trying to read from your ~/auto_tests.conf"
    sys.exit(1)

path_to_running = config.get('tests', 'path_to_running_file')
path_to_workspace = config.get('tests', 'path_to_workspace')
repo_url = config.get('tests', 'repo_url')
email = config.get('mailing', 'email')
password = config.get('mailing', 'password')
recipients = config.get('mailing', 'recipients').split(',')
smtp_server = config.get('mailing', 'smtp_server')
smtp_port = config.get('mailing', 'smtp_port')


os.chdir(path_to_running)
with open('running', 'w') as f:
    f.write('1')

try:

    os.chdir(os.path.join(path_to_workspace, 'coopbusiness', 'scripts'))
    updater = subprocess.Popen(['./script_launcher.py', 'configure'])
    updater.communicate()

    # launch tests

    tester = subprocess.Popen(['./script_launcher.py', 'test'])
    tester.communicate()

    os.chdir(os.path.join(path_to_workspace,
        'test_log', 'test_results'))
    files = sorted(os.listdir('.'), key=os.path.getctime)

    with open(files[-1], 'rb') as f:
        msg = MIMEText(f.read())

    result = ''
    with open(files[-1], 'r') as f:
        result = f.readlines()[-1]

    summary = ''
    failures = result.split()[-2]
    if failures == '0':
        summary = 'OK'
    else:
        summary = 'KO (%s)' % failures

    smtpserver = smtplib.SMTP(smtp_server, smtp_port)
    smtpserver.ehlo()
    smtpserver.starttls()
    smtpserver.ehlo()
    smtpserver.login(email, password)

    p = subprocess.Popen(['date', '+%d/%m/%Y %H:%M:%S'],
        stdout=subprocess.PIPE)
    date = p.communicate()[0]

    os.chdir(os.path.join(path_to_workspace, 'coopbusiness'))
    p = subprocess.Popen(['git', 'rev-parse', '--short', 'HEAD'],
        stdout=subprocess.PIPE)
    commit_info = p.communicate()[0]
    msg['Subject'] = '[TEST] %s, %s, %s' % (summary, date, commit_info)

    smtpserver.sendmail(email, recipients, msg.as_string())
    smtpserver.close()


finally:
    os.chdir(path_to_running)
    with open('running', 'w') as f:
        f.write('0')

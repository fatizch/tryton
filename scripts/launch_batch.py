#!/usr/bin/env python
# encoding: utf-8

import subprocess
import sys
import os
import time

if sys.argv[1] == '-k':
    subprocess.Popen("ps ax | grep celery | awk '{print $1}' | xargs kill",
        shell=True)
elif sys.argv[1] == '-r' or sys.argv[1] == '--run':
    _worker_process = subprocess.Popen('celery worker -l info '
        '--config=celeryconfig --app=trytond.modules.cog_utils.batch_launcher'
        ' --logfile=%slogs/%s.log' % (os.environ['REPOS_ROOT'],
            sys.argv[2]), shell=True)

    time.sleep(2)

    _execution = subprocess.Popen('celery call '
        'trytond.modules.cog_utils.batch_launcher.generate_all '
        '--args=\'["%s"]\'' % sys.argv[2], shell=True)

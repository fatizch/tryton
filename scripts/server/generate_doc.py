#!/usr/bin/env python
import os
import imp
import subprocess

"""
    Script to call via a repo changegroup hook to force doc build
"""

COOP_ROOT = '/home/hg/repos/coopbusiness'
DOCBUILD_DIR = '/home/hg/projects/documentation_build'

process = subprocess.Popen(['hg', 'update'], cwd=COOP_ROOT)
process.communicate()

script_launcher = imp.load_source('script_launcher', os.path.join(COOP_ROOT,
        'scripts', 'script_launcher.py'))
script_launcher.doc(override_values={
        'doc_files': DOCBUILD_DIR,
        'repo': os.path.abspath(COOP_ROOT),
        'lang': 'fr',
        'format': 'html',
        })

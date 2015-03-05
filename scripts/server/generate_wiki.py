#!/usr/bin/env python
import os
import subprocess
import shutil

"""
    Script to call via a repo changegroup hook to force doc build
"""

wiki_root = '/home/hg/repos/wiki'
process = subprocess.Popen(['hg', 'update'], cwd=wiki_root)
process.communicate()

wiki_build = '/home/hg/projects/wiki_build'
if os.path.exists(wiki_build):
    shutil.rmtree(wiki_build)

shutil.copytree(wiki_root, wiki_build)

sphinx_process = subprocess.Popen(['make', 'html'], cwd=wiki_build)
sphinx_process.communicate()

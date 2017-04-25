#!/usr/bin/env python
import os
import sys

try:
    language = sys.argv[1]
except:
    sys.stderr.write('''
Usage :
    extract_chnagelog.py <language>
''')
    sys.exit()

module_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
    '..', '..', 'modules')

for module in sorted(os.listdir(module_dir)):
    print ''
    print 'Module', module
    if not os.path.isfile(os.path.join(module_dir, module, 'doc', language,
            'features_log')):
        print '   NO CHANGELOG FOUND'
        continue
    with open(os.path.join(module_dir, module, 'doc', language,
            'features_log'), 'r') as changelog:
        for line in changelog.readlines():
            if not line.strip():
                continue
            if 'Version ' in line:
                break
            print line[:-1]

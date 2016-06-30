#!/usr/bin/env python
import os

module_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
    '..', '..', 'modules')

for module in sorted(os.listdir(module_dir)):
    print ''
    print 'Module', module
    if not os.path.isfile(os.path.join(module_dir, module, 'CHANGELOG')):
        print '   NO CHANGELOG FOUND'
        continue
    with open(os.path.join(module_dir, module, 'CHANGELOG'), 'r') as changelog:
        for line in changelog.readlines():
            if not line.strip():
                continue
            if 'Version ' in line:
                break
            print line[:-1]

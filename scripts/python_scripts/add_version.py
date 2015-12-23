#!/usr/bin/env python
import os

version_line = 'Version 1.6 - 2015-12-23\n'
module_dir = os.path.join(os.environ.get('VIRTUAL_ENV'), 'coog', 'modules')

for module in sorted(os.listdir(module_dir)):
    if not os.path.isfile(os.path.join(module_dir, module, 'CHANGELOG')):
        continue
    with open(os.path.join(module_dir, module, 'CHANGELOG'), 'r') as changelog:
        lines = changelog.read()
    with open(os.path.join(module_dir, module, 'CHANGELOG'), 'w') as changelog:
        changelog.write(version_line)
        if lines[0:7] == 'Version':
            changelog.write('\n')
        changelog.write(lines)

#!/usr/bin/env python
import os

version_line = 'Version 1.3 - 2015-01-22\n'
module_dir = os.path.join(os.environ.get('VIRTUAL_ENV'), 'tryton-workspace',
    'coopbusiness', 'modules')

for module in sorted(os.listdir(module_dir)):
    if not os.path.isfile(os.path.join(module_dir, module, 'CHANGELOG')):
        continue
    with open(os.path.join(module_dir, module, 'CHANGELOG'), 'r') as changelog:
        lines = changelog.read()
    with open(os.path.join(module_dir, module, 'CHANGELOG'), 'w') as changelog:
        changelog.write(version_line)
        changelog.write(lines)

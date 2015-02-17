#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os


if __name__ == '__main__':
    modules_dir = '../../../../coopbusiness/modules/'

    lines = []
    data = []
    for module in os.listdir(modules_dir):
        if module.endswith('translation'):
            continue
        module_dir = os.path.join(modules_dir, module, 'doc', 'fr')
        titles = []
        try:
            with open(os.path.join(module_dir, 'summary.rst'), 'r') as summ, \
                    open(os.path.join(module_dir, 'index.rst'), 'r') as index:
                data.append((index.readline(), summ.readlines()))
        except IOError:
            continue

    with open('index.rst', 'w') as output, \
            open('index_template.rst', 'r') as template:
        output.write(template.read())

        for (title, summary) in sorted(data):
            output.writelines([title, '-' * len(title), '\n'])
            output.writelines(summary + ['\n'])

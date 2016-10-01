#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from collections import OrderedDict
from itertools import groupby

SECTIONS = OrderedDict([
        ('core_coog', 'Noyau Coog\n'),
        ('custom_tryton_coog', 'Personnalisation Coog des modules Tryton\n'),
        ('transversal', 'Fonctionnalités transverses Coog\n'),
        ('laboratory', 'Laboratoire Produit\n'),
        ('contract', 'Coog transverse Assurance : Contrat\n'),
        ('endorsement', 'Avenant\n'),
        ('commission', 'Commission\n'),
        ('life', 'Prévoyance\n'),
        ('claim', 'Coog transverse Assurance : Sinistre\n'),
        ('credit', 'Coog transverse Assurance : Emprunteur\n'),
        ('health', 'Santé\n'),
        ('capital', 'Capitalisation\n'),
        ('pnc', 'IARD\n'),
        ('none', None),
])


def next_line(text):
    while True:
        line = text.readline()
        if line.strip('\n'):
            return line

if __name__ == '__main__':
    modules_dir = '../../../../coog/modules/'

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
                section = SECTIONS[next_line(index).strip('\n').strip('.. ')]
                if section:
                    module_data = (section, next_line(index), summ.readlines())
                    data.append(module_data)
        except KeyError:
            print('Bad section comment in %s/index.rst' % module_dir)
            continue
        except IOError:
            continue

    with open('index.rst', 'w') as output, \
            open('index_template.rst', 'r') as template:
        output.write(template.read())

        # Process sections in same order than they are declared above here
        for section, modules in groupby(sorted(data,
                    key=lambda x: (SECTIONS.values().index(x[0]), x[1])),
                key=lambda x: x[0]):
            output.writelines([section, '-' * len(section), '\n\n'])
            for module in modules:
                output.writelines([module[1], '^' * len(module[1]), '\n\n'])
                output.writelines(module[2] + ['\n'])

        print("Type 'make latexpdf' to generate the document.")

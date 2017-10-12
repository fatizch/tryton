#!/usr/bin/env python
# -*- encoding: utf-8 -*-
import os
import shutil
import codecs
import re
import subprocess
import unicodedata
import logging
from collections import OrderedDict
from itertools import groupby
import argparse

parser = argparse.ArgumentParser(description='Document generation script')
parser.add_argument('--output_doc_directory', help='Absolute path where the '
    'documentation will be generated', default=None, nargs='?')
args = parser.parse_args()

logging.basicConfig()
logger = logging.getLogger()


SECTIONS = OrderedDict([
        ('core_coog', 'Noyau Coog\n'),
        ('custom_tryton_coog', 'Personnalisation Coog des modules Tryton\n'),
        ('transversal', u'Fonctionnalités transverses Coog\n'),
        ('accounting', u'Comptabilité\n'),
        ('laboratory', 'Laboratoire Produit\n'),
        ('contract', 'Coog transverse Assurance : Contrat\n'),
        ('endorsement', 'Avenant\n'),
        ('commission', 'Commission\n'),
        ('life', u'Prévoyance\n'),
        ('claim', 'Coog transverse Assurance : Sinistre\n'),
        ('credit', 'Coog transverse Assurance : Emprunteur\n'),
        ('health', u'Santé\n'),
        ('capital', 'Capitalisation\n'),
        ('pnc', 'IARD\n'),
        ('none', None),
        ])

doc_path = '/tmp/'
if args.output_doc_directory:
    final_html_path = os.path.join(args.output_doc_directory, 'html')
else:
    final_html_path = os.path.join(doc_path, 'html')

coog_root = os.path.abspath(os.path.join(__file__, '..', '..', '..'))
doc_files = os.path.join(doc_path, 'coog_doc')
documentation_dir = os.path.join(coog_root, 'documentation', 'user_manual')
modules = os.path.join(coog_root, 'modules')
language = 'fr'
doc_format = 'html'
features_file = os.path.join(doc_files, 'trytond_doc', 'doc', language,
    'fonctionnalites.rst')

# Clean up previous build
if os.path.exists(doc_files):
    shutil.rmtree(doc_files)
if os.path.exists(final_html_path):
    shutil.rmtree(final_html_path)


def filter_ignore_files(_dir, filenames):
    # return files to NOT copy: any file that is outside of the doc
    # directory of target langage
    lst = [x for x in filenames if
        (not os.path.isdir(os.path.join(_dir, x)) and
            os.path.join('doc', language) not in _dir)]
    return lst


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn')


def next_line(text):
    while True:
        line = text.readline()
        if line.strip('\n'):
            return line


shutil.copytree(documentation_dir, doc_files)
modules_doc_files = os.path.join(doc_files, 'modules')
shutil.copytree(modules, modules_doc_files, ignore=filter_ignore_files)

section_data = []

for module in os.listdir(modules_doc_files):
    module_doc_path = os.path.join(modules_doc_files, module, 'doc', language)
    if not os.path.isdir(module_doc_path):
        logger.warning('Missing doc folder for module %s' % module)
        continue
    if not os.path.isfile(os.path.join(module_doc_path, 'index.rst')):
        logger.warning('Missing index.rst file for module %s' % module)
    if not os.path.isfile(os.path.join(module_doc_path, 'summary.rst')):
        logger.warning('Missing summary.rst file for module %s' % module)
    if not os.path.isfile(os.path.join(module_doc_path, 'features.rst')):
        logger.warning('Missing features.rst file for module %s' % module)
    try:
        with codecs.open(os.path.join(modules_doc_files, module, 'doc',
                    language, 'index.rst'), encoding='utf-8') as index:
            header = index.readlines()[:4]
            module_translated = [l for l in header
                if l.strip() and not l.startswith('..')][0]
            module_translated = re.sub(r'[^\w\-]+', '_',
                strip_accents(module_translated))
    except IOError:
        module_translated = module
    os.rename(os.path.join(modules_doc_files, module),
        os.path.join(modules_doc_files, module_translated))
    if module.endswith('translation'):
        continue
    try:
        with codecs.open(os.path.join(modules_doc_files, module_translated,
                    'doc', language, 'index.rst'), encoding='utf-8') as index, \
                codecs.open(os.path.join(modules_doc_files, module_translated,
                    'doc', language, 'summary.rst'), encoding='utf-8') as summ:
            section = SECTIONS[next_line(index).strip('\n').strip('.. ')]
            if section:
                module_data = (section, next_line(index), summ.readlines())
                section_data.append(module_data)
    except KeyError:
        logger.warning('Bad section comment in %s/index.rst' % module)
        continue
    except IOError:
        continue

shutil.copyfile(os.path.join(doc_files, 'index_%s.rst' % language),
    os.path.join(doc_files, 'index.rst'))

with codecs.open(features_file, 'a', encoding='utf-8') as output:
    # Process sections in same order than they are declared above here
    for section, modules in groupby(sorted(section_data,
                key=lambda x: (SECTIONS.values().index(x[0]), x[1])),
            key=lambda x: x[0]):
        output.writelines([section, '-' * len(section), '\n\n'])
        for module in modules:
            output.writelines([module[1], '^' * len(module[1]), '\n\n'])
            output.writelines(module[2] + ['\n'])

# Generate the doc
process = subprocess.Popen(['make', doc_format], cwd=doc_files)
process.communicate()

shutil.copytree(os.path.join(doc_files, '_build', 'html'), final_html_path)

logger.info('Doc generated in ' + doc_files)
logger.info('HTML folder copied to ' + final_html_path)

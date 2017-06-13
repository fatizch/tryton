#!/usr/bin/env python
import sys
import csv
import os
import polib


def override_translation(input_file, path_to_coog):
    with open(input_file, 'r') as input_f:
        for line in csv.DictReader(input_f, delimiter=','):
            translation_file = get_translation_file(path_to_coog,
                line['Module'], line['Langue'])
            if os.path.exists(translation_file):
                po_file = polib.pofile(translation_file)
            else:
                po_file = polib.POFile(wrapwidth=78)
                po_file.metadata = {
                    'Content-Type': 'text/plain; charset=utf-8',
                    }

            if os.path.exists(os.path.abspath(os.path.join(
                        path_to_coog, 'modules', line['Module']))):
                sep = ''
            else:
                sep = '%s.' % line['Module']
            msgctxt = "%s:%s:%s" % (line['Type'], line['Nom du champ'], sep)
            change_made = False
            for entry in po_file:
                if entry.msgid == line['Source'] and entry.msgctxt == msgctxt:
                    if entry.msgstr != line['Traduction'].decode('utf8'):
                        entry.msgstr = line['Traduction'].decode('utf8')
                        change_made = True
                    break
            else:
                entry = polib.POEntry(
                    msgid=line['Source'],
                    msgctxt="%s:%s:%s" % (
                        line['Type'], line['Nom du champ'], sep),
                    msgstr=line['Traduction'].decode('utf8'))
                po_file.append(entry)
                change_made = True
            if change_made:
                po_file.save(translation_file)


def get_translation_file(path_to_coog, module, language):
    if os.path.exists(os.path.abspath(
            os.path.join(path_to_coog, 'modules', module))):
        # coog module
        return os.path.abspath(os.path.join(path_to_coog,
            'modules', module, 'locale', '%s.po' % language))
    elif os.path.exists(os.path.abspath(
            os.path.join(path_to_coog, 'modules',
                '%s_cog_translation' % module))):
        # tryton module but with existing translation override
        return os.path.abspath(os.path.join(path_to_coog,
                'modules', '%s_cog_translation' % module, 'locale',
                '%s.po' % language))
    else:
        # tryton module with no translation override
        path = os.path.abspath(os.path.join, path_to_coog, 'modules',
                '%s_cog_translation' % module)
        os.makedirs(path)
        f = open(os.path.join(path, '__init__.py'), 'w')
        f.write('from trytond.pool import Pool\n\n\ndef register():\n    ')
        f.write("Pool.register(module='%s_cog_translation', type_='model')\n"
            % module)
        f.close
        f = open(os.path.join(path, 'tryton.cfg'), 'w')
        f.write('[tryton]\ndepends:\n    ir\n    res\n    %s\nxml:\n'
            % module)
        f.close
        os.makedirs(os.path.join(path, 'locale'))
        return os.path.join(path, 'locale', '%s.po' % language)


if __name__ == '__main__':
    if not len(sys.argv) == 3:
        print 'Usage : python override_translations.py input_file \
        path_to_coog'
    else:
        override_translation(sys.argv[1], sys.argv[2])

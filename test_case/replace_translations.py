#-*- coding:utf-8 -*-
import os
import sys
import polib
from trytond.ir.translation import TrytonPOFile
import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def get_modules(from_modules):
    from trytond.modules import create_graph

    modules_set = set()
    for cur_module in from_modules:
        modules_set |= set(proteus_tools.get_module_depends(cur_module))
    graph = create_graph(list(modules_set))[0]
    return [x.name for x in graph if not proteus_tools.is_coop_module(x.name)]


def replace_translations(language, update_dict, exact_dict, modules=None):
    if not modules:
        modules = [x for x in os.listdir(os.path.join(DIR, '..', 'modules'))]

    tryton_modules = get_modules(modules)

    for cur_module in tryton_modules:
        po_file = None
        path = os.path.join(DIR, '..', '..', 'trytond', 'trytond')
        if cur_module in ['ir', 'res']:
            path = os.path.join(path, cur_module)
        else:
            path = os.path.join(path, 'modules', cur_module)
        translation_file = os.path.abspath(os.path.join(path, 'locale',
            '%s.po' % language))
        if not os.path.isfile(translation_file):
            continue
        po = polib.pofile(translation_file)
        for entry in po.translated_entries():
            if (entry.msgctxt, entry.msgid, entry.msgstr) in exact_dict:
                translation = exact_dict[
                    (entry.msgctxt, entry.msgid, entry.msgstr)]
            elif (entry.msgid, entry.msgstr) in update_dict:
                translation = update_dict[(entry.msgid, entry.msgstr)]
            else:
                continue
            ttype, name, res_id = entry.msgctxt.split(':')
            entry.msgctxt = '%s:%s:%s.%s' % (ttype, name, cur_module, res_id)
            entry.msgstr = translation
            if not po_file:
                po_file = TrytonPOFile(wrapwidth=78)
                po_file.metadata = {
                    'Content-Type': 'text/plain; charset=utf-8',
                    }
            po_file.append(entry)

        if not po_file:
            continue
        po_file.sort()
        translation_module = '%s_cog_translation' % cur_module
        path = os.path.abspath(os.path.join(DIR, '..', 'modules',
                translation_module))
        if not os.path.exists(path):
            os.makedirs(path)
            f = open(os.path.join(path, '__init__.py'), 'w')
            f.write('from trytond.pool import Pool\n\n\ndef register():\n')
            f.write("    Pool.register(module='%s', type_='model')\n"
                % translation_module)
            f.close
            f = open(os.path.join(path, 'tryton.cfg'), 'w')
            f.write('[tryton]\ndepends:\n    ir\n    res\n    %s\nxml:\n'
                % cur_module)
            f.close
        if not os.path.exists(os.path.join(path, 'locale')):
            os.makedirs(os.path.join(path, 'locale'))
        the_file = open(os.path.join(path, 'locale', '%s.po' % language),
            'w')
        the_file.write(unicode(po_file).encode('utf-8'))
        the_file.close


if __name__ == '__main__':
    modules = None
    if len(sys.argv) == 2:
        modules = [sys.argv[2]]
    update_dict = {
        ('Party', 'Tiers'): 'Acteur',
        ('Parties', 'Tiers'): 'Acteurs',
        ('Street', 'Rue'): 'Rue (Ligne 4)',
        ('Street (bis)', 'Rue (bis)'): u'Boîte Postale (Ligne 5)',
        ('Invoice', 'Facture'): 'Quittance',
        ('Invoices', 'Factures'): 'Quittances',
        ('Invoice Lines', 'Lignes de facture'): 'Lignes de quittance',
        ('Invoice Line', 'Ligne de Facture'): 'Ligne de quittance',
        ('Posted', u'Posté'): 'Emis',
        ('Post', 'Poster'): 'Emettre',
        ('_Post', '_Poster'): 'Emettre',
        }
    update_exact_dict = {
        ('selection:account.invoice,state:', 'Posted', u'Posté'): 'Emise',
        ('field:party.address,name:', 'Name', 'Nom'): 'Ligne 2',
        }
    replace_translations('fr_FR', update_dict, update_exact_dict, modules)

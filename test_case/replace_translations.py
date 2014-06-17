#-*- coding:utf-8 -*-
import os
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


def replace_translations(test_config_file, language, update_dict,
        path_to_store_file=None):
    cfg_dict = proteus_tools.get_test_cfg(test_config_file)
    proteus_tools.get_config(cfg_dict)
    modules = get_modules(cfg_dict['modules'])

    po_file = TrytonPOFile(wrapwidth=78)
    po_file.metadata = {'Content-Type': 'text/plain; charset=utf-8'}

    for cur_module in modules:
        translation_file = os.path.abspath(os.path.join(DIR, '..', '..',
            'trytond', 'trytond', 'modules', cur_module, 'locale',
            '%s.po' % language))
        if not os.path.isfile(translation_file):
            continue
        po = polib.pofile(translation_file)
        for entry in po.translated_entries():
            if not (entry.msgid, entry.msgstr) in update_dict:
                continue
            ttype, name, res_id = entry.msgctxt.split(':')
            entry.msgctxt = '%s:%s:%s.%s' % (ttype, name, cur_module, res_id)
            entry.msgstr = update_dict[(entry.msgid, entry.msgstr)]
            po_file.append(entry)

    po_file.sort()
    if not path_to_store_file:
        path_to_store_file = DIR
    the_file = open(os.path.join(path_to_store_file, '%s.po' % language), 'w')
    the_file.write(unicode(po_file).encode('utf-8'))
    the_file.close


if __name__ == '__main__':
    update_dict = {
        ('Party', 'Tiers'): 'Acteur',
        ('Parties', 'Tiers'): 'Acteurs',
        ('Street', 'Rue'): 'Rue (Ligne 4)',
        ('Street (bis)', 'Rue (bis)'): u'Boîte Postale (Ligne 5)',
        ('Invoice', 'Facture'): 'Quittance',
        ('Invoices', 'Factures'): 'Quittances',
        }
    replace_translations(os.path.join(DIR, 'test_case.cfg'), 'fr_FR',
        update_dict, os.path.abspath(os.path.join(DIR, '..',
                'modules', 'cog_translation', 'locale')))

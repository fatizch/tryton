import os
import argparse
from proteus import config, Model, Wizard


def unfuzzy(lang, module):
    Translation = Model.get('ir.translation')
    domain = [('lang', '=', lang.code), ('fuzzy', '=', True),
        ('module', '=', module)]
    fuzzy_translations = []
    for translation in Translation.find(domain):
        fuzzy_translations.append(translation.id)
        print('fuzzy:%s:%s:%s => %s' % (module, translation.name,
                translation.src, translation.value))
    Translation.write(fuzzy_translations, {'fuzzy': False}, {})


def generate(lang, module):
    unfuzzy(lang, module)
    ExportWizard = Wizard('ir.translation.export')
    wiz_form = ExportWizard.form
    wiz_form.language = lang
    Module = Model.get('ir.module')
    wiz_form.module, = Module.find([('name', '=', module)])
    ExportWizard.execute('export')
    return ExportWizard.form.file


def get_lang(lang):
    Language = Model.get('ir.lang')
    cur_lang, = Language.find([('code', 'like', '%s%%' % lang)])
    return cur_lang


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate translations')
    parser.add_argument('--config', '-c', required=True,
        help='trytond config file')
    parser.add_argument('--path', '-p', required=True,
        help='modules folder')
    parser.add_argument('--lang', '-l', default='fr',
        help='translations language')
    parser.add_argument('--modules', '-m', nargs='+',
        help='modules to translate')
    args = parser.parse_args()
    config.set_trytond(config_file=args.config)
    lang = get_lang(args.lang)
    for module in args.modules:
        if module in ('ir', 'res'):
            continue
        print('### start generating %s ###' % module)
        try:
            res = generate(lang, module)
        except Exception as e:
            print(e)
            print('### generation failed ###')
            print('')
            continue
        if res:
            po_dir = os.path.join(args.path, module, 'locale')
            if not os.path.exists(po_dir):
                os.mkdir(po_dir)
            po_path = os.path.join(po_dir, '%s.po' % lang.code)
            with open(po_path, 'w') as po_file:
                po_file.write(res)
            print('### generation done, saved to %s ###' % po_path)
        else:
            print('### generation failed ###')
        print('')

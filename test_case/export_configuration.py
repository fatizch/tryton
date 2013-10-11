import os
import time
import logging

import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))
CODE_TEMPLATE = '''def export(cfg_dict):
    from %s import export_configuration

    export_configuration(cfg_dict)

export(cfg_dict)
'''
logging.getLogger('export_config').setLevel(logging.INFO)


def export_configurations(test_config_file):
    cfg_dict = proteus_tools.get_test_cfg(test_config_file)
    proteus_tools.get_config(cfg_dict)
    for cur_module in os.listdir(os.path.join(DIR, '..', 'modules')):
        cur_path = os.path.abspath(
            os.path.join(DIR, '..', 'modules', cur_module, 'scripts'))
        if os.path.exists(cur_path):
            start = time.clock()
            for f in [f for f in os.listdir(cur_path)
                    if f.endswith('.py') and f != '__init__.py']:
                logging.getLogger('export_config').info(
                    'Exporting %s for module %s' % (f, cur_module))
                code = CODE_TEMPLATE % ('trytond.modules.' + cur_module
                    + '.scripts')
                context = {'cfg_dict': cfg_dict}
                localcontext = {}
                exec code in context, localcontext
            logging.getLogger('export_config').info(
                '  -> Export configuration for module %s in %s s' %
                (cur_module, time.clock() - start))


if __name__ == '__main__':
    export_configurations(os.path.join(DIR, 'test_case.cfg'))

# -*- coding: utf-8 -*-
import os
import proteus_tools


DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def configure_proteus(test_config_file=None):
    if not test_config_file:
        test_config_file = os.path.join(DIR, 'test_case.cfg')
    cfg_dict = proteus_tools.get_test_cfg(test_config_file)
    return proteus_tools.get_config(cfg_dict)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from proteus import Model
import proteus_tools


def update_models(cfg_dict):
    cfg_dict['Lang'] = Model.get('ir.lang')


def set_language_translatable(cfg_dict, code):
    domain = [
        ('translatable', '=', False),
        ('code', '=', code),
    ]
    lang = proteus_tools.get_objects_from_db(cfg_dict, 'Lang', domain=domain)
    if not lang:
        return
    lang.translatable = True
    lang.save()


def launch_test_case(cfg_dict):
    update_models(cfg_dict)
    set_language_translatable(cfg_dict, 'fr_FR')
    set_language_translatable(cfg_dict, 'en_US')

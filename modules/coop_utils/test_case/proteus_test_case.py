#!/usr/bin/env python
# -*- coding: utf-8 -*-

from proteus import Model
import proteus_tools

#def load_dictionnary(cfg_dict):
#    path = os.path.join(cfg_dict['dir_loc'], 'insurer')
#    reader = csv.reader(open(path, 'rb'), delimiter=';')
#    if not 'dictionnary' in cfg_dict:
#        cfg_dict['dictionnary'] = {}
#    for entry in reader:
#        cfg_dict['dictionnary'][entry[0]] = entry[1]
#    return cfg_dict
#
#
#def get_object_from_db(cfg_dict, model, key=None, value=None, domain=None):
#    if not domain:
#        domain = []
#    if not key:
#        key = 'name'
#    if value:
#        domain.append((key, '=', value))
#    instances = cfg_dict[model].find(domain, limit=1)
#    if instances:
#        return instances[0]
#
#
#def get_or_create_instance(cfg_dict, model, key=None, value=None):
#    res = get_object_from_db(cfg_dict, model, key, value)
#    if not res:
#        res = cfg_dict[model]()
#        setattr(res, key, value)
#        res.save()
#    return res
#
#
#def create_translation(cfg_dict, model, key=None, value=None):
#    translation = translate(cfg_dict, value)
#    if not translation or translation == value:
#        return None
#    res = Model.get('ir.translation')()
#    res.lang = cfg_dict.get('language', 'fr_FR')
#    res.src = value
#    res.name = '%s,%s' % model, key
#    res.value = translation
#    res.type = model
#    res.save()
#
#
#def translate(cfg_dict, name):
#    if name in cfg_dict['dictionnary']:
#        return cfg_dict['dictionnary'][name]
#    return name
#
#
#def create_groups(cfg_dict):
#    ind_contract = get_or_create_instance('res.group',
#        value='Individual Contract Management')


def update_models(cfg_dict):
    cfg_dict['Model'] = Model.get('ir.model')
    cfg_dict['Lang'] = Model.get('ir.lang')


def set_global_search_options(cfg_dict):
    for model_name in cfg_dict['models'].strip().splitlines():
        model = proteus_tools.get_objects_from_db(
            cfg_dict, 'Model', 'model', model_name, force_search=True)
        if not model.global_search_p:
            model.global_search_p = True
            model.save()


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
    set_global_search_options(cfg_dict)
    set_language_translatable(cfg_dict, 'fr_FR')
    set_language_translatable(cfg_dict, 'en_US')

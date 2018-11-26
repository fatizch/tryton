# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re
from unidecode import unidecode
from trytond.pool import Pool
from trytond.transaction import Transaction

from . import utils

import logging
LOG = logging.getLogger(__name__)

__all__ = []


FMT = {0: 'b', 1: 'u', 2: 'i'}


def format_number(percent, value, lang=None):
    Lang = Pool().get('ir.lang')
    if not lang:
        lang = utils.get_user_language()
    return Lang.format(lang, percent, value)


def get_instance_summary(instance, label, at_date, lang):
    if not hasattr(instance, 'get_summary_content'):
        return None
    return instance.get_summary_content(label, at_date, lang)


def get_field_summary(instance, var_name, label, at_date=None, lang=None):
    value = getattr(instance, var_name)
    if value is None:
        return None
    if type(value) is tuple:
        if not isinstance(label, str):
            label = translate_label(instance, var_name, lang)
            values = utils.get_good_versions_at_date(instance, var_name,
                                                     at_date)
        return (label, [get_instance_summary(i, None, at_date, lang)
                        for i in values])
    else:
        if label is True:
            label = translate_label(instance, var_name, lang)
        instance_summary = get_instance_summary(value, label, at_date, lang)

        if instance_summary is not None:
            return instance_summary
    return (label, translate_value(instance, var_name, lang))


def generate_summaries(to_format):
    summaries = [generate_summary(elem) for elem in to_format]
    return '\n\n'.join(summaries)


def generate_summary(desc, level=0):
    level_fmt = FMT.get(level, None)
    node_types = (tuple, list)
    assert type(desc) in node_types and len(desc) == 2, desc
    label, value = desc
    assert not (label is None and type(value) in node_types)
    res = '<div>%s' % (max(level - 1, 0) * 4 * ' ')
    if label is not None:
        if level_fmt is None:
            res += label
        else:
            res += '<%s>%s</%s>' % (level_fmt, label, level_fmt)

    if not (label is None or type(value) in node_types):
        res += ': '
    if type(value) in node_types:
        if len(value) > 0:
            res += '</div>%s' % ''.join([generate_summary(i, level + 1)
                    for i in value if i is not None])
        else:
            res += '</div>'
    else:
        res += '%s</div>' % value
    return res


def translate_label(instance, var_name, lang=None):
    field = instance._fields[var_name]
    # function field
    if not hasattr(field, 'string') and hasattr(field, 'field'):
        string = field.field.string
    else:
        string = field.string
    return translate_field(instance, var_name, string, lang=lang)


def translate_value(instance, var_name, lang=None):
    field = getattr(instance.__class__, var_name)
    if hasattr(field, '_field'):
        _type = field._field.__class__._type
    else:
        _type = field.__class__._type

    ttype = None
    if _type == 'selection':
        res = selection_as_string(instance.__class__, var_name,
            getattr(instance, var_name))
        ttype = field.__class__._type
    elif _type == 'date':
        Date = Pool().get('ir.date')
        res = Date.date_as_string(getattr(instance, var_name), lang)
    elif _type == 'dict':
        CDataDef = Pool().get('extra_data')
        res = CDataDef.get_extra_data_summary([instance],
            var_name)[instance.id]
    else:
        res = '%s' % getattr(instance, var_name)
    if (hasattr(field, 'translate') and field.translate
            or (hasattr(field, 'translate_selection')
                and field.translate_selection)):
        try:
            return translate_field(instance, var_name, res, ttype, lang=lang)
        except KeyError:
            return getattr(instance, var_name)
    return res


def translate_field(instance, var_name, src, ttype='field', lang=None):
    return translate(instance, var_name, src, ttype, lang=lang)


def translate(model, var_name, src, ttype, lang=None):
    Translation = Pool().get('ir.translation')
    language = lang.code if lang else Transaction().language
    target = '%s%s' % (model.__name__, ',%s' % var_name if var_name else '')
    try:
        return Translation.get_source(target, ttype, language, src) or src
    except ValueError:
        return src


def translate_bool(value, lang=None):
    language = lang.code if lang else Transaction().language
    if language == 'fr':
        return 'Vrai' if value else 'Faux'
    return str(value)


def translate_model_name(model, lang=None):
    return translate(model, 'name', model._get_name(), ttype='model',
        lang=lang)


def selection_as_string(cls, var_name, value):
    field = getattr(cls, var_name)
    if hasattr(field, '_field'):
        selection = field._field.selection
    else:
        selection = field.selection
    if type(selection) is str:
        selection = getattr(cls, selection)()
    for cur_tuple in selection:
        if cur_tuple[0] == value:
            return cur_tuple[1]


def asciify(text):
    if type(text) == str:
        return text
    return str(unidecode(text)) if text else ''


def slugify(text, char='_', lower=True):
    res = re.sub(r'[^\w\-]+', char, asciify(text))
    return res.lower() if lower else res


def is_ascii(s):
    try:
        s.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False


def get_print_infos(lst, obj_name=None):
    length = len(lst)
    if length == 1:
        min_max = ': %s' % lst
    elif length > 1:
        min_max = ': %s...%s' % (str(lst[0]), str(lst[-1]))
    else:
        min_max = ''
    return '%d %s%s%s' % (length, obj_name or 'obj',
        's' if length > 1 else '', min_max)

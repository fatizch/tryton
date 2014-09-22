# -*- coding: utf-8 -*-
import re

from trytond.pool import Pool
from trytond.transaction import Transaction

import utils


__all__ = []


def format_number(percent, value, lang=None):
    Lang = Pool().get('ir.lang')
    if not lang:
        lang = utils.get_user_language()
    return Lang.format(lang, percent, value)


def zfill(the_instance, val_name):
    size = utils.get_field_size(the_instance, val_name)
    if size:
        val = getattr(the_instance, val_name)
        if not val:
            val = ''
        return val.zfill(size)


def re_indent_text(src, indent):
    return '%s\n' % '\n'.join((4 * ' ' * indent) + i for i in src.splitlines())


def get_field_as_summary(instance, var_name, with_label=True, at_date=None,
        lang=None):
    if not getattr(instance, var_name):
        return ''
    res = ''
    if type(getattr(instance, var_name)) is tuple:
        list_at_date = utils.get_good_versions_at_date(
            instance, var_name, at_date)
        for element in list_at_date:
            if not hasattr(element.__class__, 'get_summary'):
                continue
            sub_indent = 0
            if res != '':
                res += '\n'
            if with_label:
                if res == '':
                    res = '<b>%s :</b>\n' % translate_label(
                        instance, var_name, lang=lang)
                sub_indent = 1
            summary_dict = element.get_summary(
                [element], name=var_name, at_date=at_date, lang=lang)
            if summary_dict and element.id in summary_dict:
                res += re_indent_text(
                    '%s\n' % summary_dict[element.id], sub_indent)
    else:
        if with_label:
            res = '%s : ' % translate_label(instance, var_name, lang=lang)
        if hasattr(getattr(instance, var_name).__class__, 'get_summary'):
            summary_dict = getattr(instance, var_name).__class__.get_summary(
                [instance], at_date=at_date, lang=lang)
            value = summary_dict[instance.id]
        else:
            value = translate_value(instance, var_name)
        res += '%s\n' % value
    return re_indent_text(res, 0)


def translate_label(instance, var_name, lang=None):
    field = instance._fields[var_name]
    #function field
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
        res = selection_as_string(instance.__class__, var_name, getattr(instance, var_name))
        ttype = field.__class__._type
    elif _type == 'date':
        res = date_as_string(getattr(instance, var_name), lang)
    elif _type == 'dict':
        CDataDef = Pool().get('extra_data')
        res = CDataDef.get_extra_data_summary([instance],
            var_name)[instance.id]
    else:
        res = u'%s' % getattr(instance, var_name)
    if (hasattr(field, 'translate') and field.translate
            or (hasattr(field, 'translate_selection')
                and field.translate_selection)):
        return translate_field(instance, var_name, res, ttype, lang=lang)
    return res


def translate_field(instance, var_name, src, ttype='field', lang=None):
    return translate(instance, var_name, src, ttype, lang=lang)


def translate(model, var_name, src, ttype, lang=None):
    Translation = Pool().get('ir.translation')
    language = lang.code if lang else Transaction().language
    target = '%s%s' % (model.__name__, ',%s' % var_name if var_name else '')
    res = Translation.get_source(target, ttype, language, src)
    if not res:
        return src
    return res


def translate_bool(value, lang=None):
    language = lang.code if lang else Transaction().language
    if language == 'fr_FR':
        return 'Vrai' if value else 'Faux'
    return str(value)


def translate_model_name(model, lang=None):
    return translate(model, 'name', model._get_name(), ttype='model',
        lang=lang)


def get_descendents_name(from_class):
    result = []
    for model_name, model in Pool().iterobject():
        if issubclass(model, from_class):
            if model.__doc__:
                result.append((model_name, translate_model_name(model)))
            else:
                raise Exception('Model %s does not have a docstring !' %
                    model_name)
    return result


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


def date_as_string(date, lang=None):
    Lang = Pool().get('ir.lang')
    if not lang:
        lang = utils.get_user_language()
    return Lang.strftime(date, lang.code, lang.date)


def remove_invalid_char(from_string):
    import unicodedata
    res = ''.join((c for c in unicodedata.normalize('NFD',
                unicode(from_string)) if unicodedata.category(c) != 'Mn'))
    res = re.sub('[^0-9a-zA-Z]+', '_', res)
    return res


def remove_all_but_alphanumeric_and_space(from_string):
    pattern = re.compile(r'([^\s\w]|_)+')
    return pattern.sub('', from_string)


def remove_blank_and_invalid_char(from_string, lower_case=True):
    res = remove_invalid_char(from_string).replace(' ', '_')
    return res.lower() if lower_case else res


def is_ascii(s):
    try:
        s.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False


def check_for_pattern(s, pattern):
    if s is not None:
        s = s.strip()
        matchObj = re.match(pattern, s)
        if matchObj:
            return matchObj.group()
        return False

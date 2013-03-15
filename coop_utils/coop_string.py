# -*- coding: utf-8 -*-
import re

from trytond.pool import Pool
from trytond.transaction import Transaction

import utils


def zfill(the_instance, val_name):
    size = utils.get_field_size(the_instance, val_name)
    if size:
        val = getattr(the_instance, val_name)
        if not val:
            val = ''
        return val.zfill(size)


def re_indent_text(src, indent):
    return '%s\n' % "\n".join((4 * ' ' * indent) + i for i in src.splitlines())


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
            summary_dict = element.__class__.get_summary(
                [element], name=var_name, at_date=at_date, lang=lang)
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
    field = getattr(instance.__class__, var_name)
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
        value = selection_as_string(instance, var_name)
        ttype = field.__class__._type
    elif _type == 'date':
        value = date_as_string(getattr(instance, var_name), lang)
    else:
        value = str(getattr(instance, var_name))
    if (hasattr(field, 'translate') and field.translate
        or (hasattr(field, 'translate_selection')
            and field.translate_selection)):
        return translate_field(instance, var_name, value, ttype, lang=lang)
    return str(value)


def translate_field(instance, var_name, src, ttype='field', lang=None):
    return translate(instance.__class__, var_name, src, ttype, lang=lang)


def translate(model, var_name, src, ttype, lang=None):
    if lang:
        language = lang.code
    else:
        language = Transaction().language
    Translation = Pool().get('ir.translation')
    res = Translation.get_source(
        '%s,%s' % (model.__name__, var_name), ttype, language, src)
    if not res:
        return src
    return res


def translate_model_name(model, lang=None):
    return translate(
        model, 'name', model._get_name(), ttype='model', lang=lang)


def get_descendents_name(from_class):
    result = []
    for model_name, model in Pool().iterobject():
        if issubclass(model, from_class):
            if model.__doc__:
                result.append((model_name, translate_model_name(model)))
            else:
                raise Exception(
                    'Model %s does not have a docstring !' % model_name)
    return result


def selection_as_string(instance, var_name):
    field = getattr(instance.__class__, var_name)
    if hasattr(field, '_field'):
        selection = field._field.selection
    else:
        selection = field.selection
    if type(selection) is str:
        selection = getattr(instance.__class__, selection)()
    for cur_tuple in selection:
        if cur_tuple[0] == getattr(instance, var_name):
            return cur_tuple[1]


def date_as_string(date, lang=None):
    Lang = Pool().get('ir.lang')
    if not lang:
        lang = utils.get_user_language()
    return Lang.strftime(date, lang.code, lang.date)


def remove_invalid_char(from_string):
    import unicodedata
    res = ''.join((
        c for c in unicodedata.normalize('NFD', unicode(from_string))
        if unicodedata.category(c) != 'Mn'))
    res = re.sub('[^0-9a-zA-Z]+', '_', res)
    return res


def remove_all_but_alphanumeric_and_space(from_string):
    import re
    pattern = re.compile(r'([^\s\w]|_)+')
    return pattern.sub('', from_string)


def remove_blank_and_invalid_char(from_string, lower_case=True):
    res = remove_invalid_char(from_string).replace(' ', '_')
    if lower_case:
        res = res.lower()
    return res


def concat_strings(this, that):
    res = ''
    if this and that:
        res = '%s %s' % (this, that)
    elif this:
        res = this
    elif that:
        res = that
    return res


def is_ascii(s):
    try:
        s.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

import utils as utils

from trytond.pool import Pool

from trytond.transaction import Transaction


def zfill(the_instance, val_name):
    size = utils.get_field_size(the_instance, val_name)
    if size:
        val = getattr(the_instance, val_name)
        if not val:
            val = ''
        return val.zfill(size)


def re_indent_text(src, indent):
    return '%s\n' % "\n".join((4 * ' ' * indent) + i for i in src.splitlines())


def get_field_as_summary(instance, var_name, with_label=True, at_date=None):

    if not getattr(instance, var_name):
        return ''
    res = ''
    if type(getattr(instance, var_name)) is tuple:
        list_at_date = utils.get_good_versions_at_date(instance, var_name,
            at_date)
        for element in list_at_date:
            if not hasattr(element, 'get_summary'):
                continue
            sub_indent = 0
            if res != '':
                res += '\n'
            if with_label:
                if res == '':
                    res = '<b>%s :</b>\n' % translate_label(instance, var_name)
                sub_indent = 1
            res += re_indent_text('%s\n' % element.get_summary(name=var_name,
                    at_date=at_date),
                sub_indent)
    else:
        if with_label:
            res = '%s : ' % translate_label(instance, var_name)
        if hasattr(getattr(instance, var_name), 'get_summary'):
            value = getattr(instance, var_name).get_summary(at_date=at_date)
        else:
            value = translate_value(instance, var_name)
        res += '%s\n' % value
    return re_indent_text(res, 0)


def translate_label(instance, var_name):
    field = getattr(instance.__class__, var_name)
    return translate_field(instance, var_name, field.string)


def translate_value(instance, var_name):
    field = getattr(instance.__class__, var_name)
    if hasattr(field, '_field'):
        _type = field._field.__class__._type
    else:
        _type = field.__class__._type
    if _type == 'selection':
        value = selection_as_string(instance, var_name)
        ttype = field.__class__._type
    else:
        value = str(getattr(instance, var_name))
        ttype = None
    if (hasattr(field, 'translate') and field.translate
        or (hasattr(field, 'translate_selection')
            and field.translate_selection)):
        return translate_field(instance, var_name, value, ttype)
    return str(value)


def translate_field(instance, var_name, src, ttype='field'):
    return translate(instance.__class__, var_name, src, ttype)


def translate(model, var_name, src, ttype):
    Translation = Pool().get('ir.translation')
    res = Translation.get_source(
            '%s,%s' % (model.__name__, var_name),
             ttype,
             Transaction().language,
             src)
    if not res:
        return src
    return res


def translate_model_name(model):
    return translate(model, 'name', model.__doc__, ttype='model')


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

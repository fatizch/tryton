import copy

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.wizard import Wizard
from trytond.pool import Pool


class CoopSQL(ModelSQL):
    pass


class CoopView(ModelView):
    pass


class CoopWizard(Wizard):
    pass


def get_descendents(from_class):
    res = []
    cur_models = [model_name
                  for model_name, model in Pool().iterobject()
                  if issubclass(model, from_class)]
    Model = Pool().get('ir.model')
    models = Model.search([('model', 'in', cur_models)])
    for cur_model in models:
        res.append([cur_model.model, cur_model.name])
    return res


def get_descendents_name(from_class):
    result = []
    for model_name, model in Pool().iterobject():
        if issubclass(model, from_class):
            result.append((model_name, model.__doc__.splitlines()[0]))
    return result


class DynamicSelection(ModelSQL, ModelView):
    'Dynamic Selection'

    __name__ = 'coop.dynamic_selection'

    kind = fields.Selection([('person_relation', 'Person Relation'),
                             ('company_relation', 'Company Relation')],
                            'Kind', required=True)
    key = fields.Char('Key', required=True)
    name = fields.Char('Value', required=True)
    reverse_key = fields.Char('Reverse Key')

    @classmethod
    def __setup__(cls):
        super(DynamicSelection, cls).__setup__()
        cls._sql_constraints += [
            ('key_uniq', 'UNIQUE(key)', 'The key must be unique!'),
        ]


def get_dynamic_selection(kind):
    res = []
    DynamicSelection = Pool().get('coop.dynamic_selection')
    dyn_sels = DynamicSelection.search([('kind', '=', kind)])
    for dyn_sel in dyn_sels:
        res.append([dyn_sel.key, dyn_sel.name])
    return res


def get_reverse_dynamic_selection(key):
    res = []
    DynamicSelection = Pool().get('coop.dynamic_selection')
    dyn_sels = DynamicSelection.search([('reverse_key', '=', key)],
                                       limit=1)
    for dyn_sel in dyn_sels:
        res.append([dyn_sel.key, dyn_sel.name])
    return res


def get_module_name(cls):
    return cls.__name__.split('.')[0]


def change_relation_links(cls, from_module, to_module):
    for field_name in dir(cls):
        field = getattr(cls, field_name)
        attr_name = ''
        if hasattr(field, 'model_name'):
            attr_name = 'model_name'
        if hasattr(field, 'relation_name'):
            attr_name = 'relation_name'
        if attr_name == '':
            continue
        model_name = getattr(field, attr_name)
        if not model_name.startswith(from_module):
            continue
        setattr(field, attr_name,
            to_module + model_name.split(from_module)[1])
        setattr(cls, field_name, field)

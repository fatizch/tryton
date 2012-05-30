from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pool import Pool


def get_descendents(from_class):
    res = []
    cur_models = [model_name
                  for model_name, model in Pool().iterobject()
                  if isinstance(model, from_class)]
    model_obj = Pool().get('ir.model')
    model_ids = model_obj.search([
        ('model', 'in', cur_models),
        ])
    for model in model_obj.browse(model_ids):
        res.append([model.model, model.name])
    return res


def get_descendents_name(from_class):
    result = []
    for model_name, model in Pool().iterobject():
        if isinstance(model, from_class):
            result.append((model_name, model._description))
    return result


class curry:
    def __init__(self, fun, *args, **kwargs):
        self.fun = fun
        self.pending = args[:]
        self.kwargs = kwargs.copy()

    def __call__(self, *args, **kwargs):
        if kwargs and self.kwargs:
            kw = self.kwargs.copy()
            kw.update(kwargs)
        else:
            kw = kwargs or self.kwargs

        return self.fun(*(self.pending + args), **kw)


class DynamicSelection(ModelSQL, ModelView):
    'Dynamic Selection'

    _description = __doc__
    _name = 'coop.dynamic_selection'

    kind = fields.Selection([('person_relation', 'Person Relation'),
                             ('company_relation', 'Company Relation')],
                            'Kind', required=True)
    key = fields.Char('Key', required=True)
    name = fields.Char('Value', required=True)
    reverse_key = fields.Char('Reverse Key')

    def __init__(self):
        super(DynamicSelection, self).__init__()
        self._sql_constraints += [
            ('key_uniq', 'UNIQUE(key)', 'The key must be unique!'),
        ]

DynamicSelection()


def get_dynamic_selection(kind):
        res = []
        relation_obj = Pool().get('coop.dynamic_selection')
        rel_ids = relation_obj.search([('kind', '=', kind)])
        for rel_obj in relation_obj.browse(rel_ids):
            res.append([rel_obj.key, rel_obj.name])
        return res


def get_reverse_dynamic_selection(key):
        res = []
        relation_obj = Pool().get('coop.dynamic_selection')
        rel_ids = relation_obj.search([('reverse_key', '=', key)], limit=1)
        for rel_obj in relation_obj.browse(rel_ids):
            res.append([rel_obj.key, rel_obj.name])
        return res

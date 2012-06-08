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
    @classmethod
    def __setup__(cls, fun, *args, **kwargs):
        cls.fun = fun
        cls.pending = args[:]
        cls.kwargs = kwargs.copy()

    def __call__(self, *args, **kwargs):
        if kwargs and self.kwargs:
            kw = self.kwargs.copy()
            kw.update(kwargs)
        else:
            kw = kwargs or self.kwargs

        return self.fun(*(self.pending + args), **kw)


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

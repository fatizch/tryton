from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL


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

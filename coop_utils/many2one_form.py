import copy

from trytond.model import fields
from trytond.pool import Pool


class Many2OneForm(fields.Function):
    '''
    Define One2Many based on a Many2One.
    The One2Many can be used to display the Many2One in Form view.
    Must be created in __setup__ to get the right many2one instance.
    '''

    def __init__(self, many2one, loading='eager'):
        field = fields.One2Many(many2one.model_name, None, many2one.string,
            datetime_field=many2one.datetime_field, size=1, help=many2one.help,
            required=many2one.required, readonly=many2one.readonly,
            domain=many2one.domain, states=many2one.states,
            depends=many2one.depends, order_field=many2one.order_field,
            context=many2one.context)
        super(Many2OneForm, self).__init__(field, many2one.name,
            setter=many2one.name, searcher=many2one.name, loading=loading)
        self.many2one = many2one

    def __setattr__(self, name, value):
        super(Many2OneForm, self).__setattr__(name, value)
        if name == 'name':
            # many2one.name is None at the __init__
            self.getter = value
            self.setter = value
            self.searcher = value
            self._field.readonly = False

    def __copy__(self):
        return Many2OneForm(copy.copy(self.many2one), loading=self.loading)

    def __deepcopy__(self, memo):
        return Many2OneForm(copy.deepcopy(self.many2one, memo),
            loading=self.loading)

    def search(self, model, name, clause):
        return (self.many2one.name,) + tuple(clause[1:])

    def get(self, ids, model, name, values=None):
        result = dict((i, []) for i in ids)
        values = model.read(ids, [self.many2one.name])
        for record in values:
            value = record[self.many2one.name]
            if value:
                result[record['id']] = [value]
        if isinstance(name, list):
            return dict((n, result) for n in name)
        else:
            return {name: result}

    def set(self, ids, model, name, values):
        pool = Pool()
        Target = pool.get(self.model_name)
        records = model.browse(ids)
        for action in values:
            if action[0] == 'create':
                new_target = Target.create(action[1])
                model.write(records, {
                        self.many2one.name: new_target,
                        })
            elif action[0] == 'write':
                Target.write(Target.browse(action[1]), action[2])
            elif action[0] == 'delete':
                Target.delete(Target.browse(action[1]))
            elif action[0] == 'delete_all':
                Target.delete(Target.browse(
                        self.get(ids, model, name)[name].values()))
            elif action[0] in ('unlink', 'unlink_all'):
                model.write(records, {
                        self.many2one.name: None,
                        })
            elif action[0] in ('add', 'set'):
                model.write(records, {
                        self.many2one.name: int(action[1][0]),
                        })
            else:
                raise Exception('Bad arguments')

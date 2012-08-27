import copy
from functools import wraps

from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool


class ReferenceForm(fields.Function):
    '''
    Define One2Many based on a Reference
    The One2Many can be used to display the Reference in Form view.
    '''

    def __init__(self, reference, target, states=None, depends=None,
            loading='eager'):
        field = fields.One2Many(target, None, reference.string, states=states,
            depends=depends, size=1)
        super(ReferenceForm, self).__init__(field,
            (reference.name, target),
            setter=(reference.name, target),
            searcher=(reference.name, target), loading=loading)
        self.reference = reference
        self.target = target

    def __setattr__(self, name, value):
        super(ReferenceForm, self).__setattr__(name, value)
        if name == 'name':
            # reference.name is None at __init__
            self.getter = (value, self.target)
            self.setter = (value, self.target)
            self.searcher = (value, self.target)
            self._field.readonly = False

    def __copy__(self):
        return ReferenceForm(copy.copy(self.reference), self.target,
            loading=self.loading)

    def __deepcopy__(self, memo):
        return ReferenceForm(copy.deepcopy(self.reference, memo),
            self.target,
            loading=self.loading)

    def search(self, model, name, clause):
        return (self.reference.name, clause[1], (self.target, clause[2]))

    def get(self, ids, model, name, values=None):
        result = dict((i, []) for i in ids)
        values = model.read(ids, [self.reference.name])
        for record in values:
            value = record[self.reference.name]
            if value:
                target, id_ = value.split(',')
                if target == self.target and id_:
                    result[record['id']] = [int(id_)]
        if isinstance(name, list):
            return dict((n, result) for n in name)
        else:
            return {name: result}

    def set(self, ids, model, name, values):
        pool = Pool()
        Target = pool.get(self.target)
        records = model.browse(ids)
        for action in values:
            if action[0] == 'create':
                new_target = Target.create(action[1])
                model.write(records, {
                        self.reference.name: str(new_target),
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
                        self.reference.name: None,
                        })
            elif action[0] in ('add', 'set'):
                model.write(records, {
                        self.reference.name: str(Target(int(action[1][0]))),
                        })
            else:
                raise Exception('Bad arguments')

    @staticmethod
    def expand_reference(cls, field_name):
        '''
        Expand Reference field into many One2Many fields.
        Reference must use a list of selection.
        It must be called in Model.__setup__
        '''
        field = getattr(cls, field_name)
        expand_field_selection_name = '%s_selection' % field_name
        if not getattr(cls, expand_field_selection_name, None):
            selection = fields.Function(
                fields.Selection(field.selection, field.string,
                    on_change=[field_name, expand_field_selection_name],
                    on_change_with=[field_name]),
                'on_change_with_%s' % expand_field_selection_name,
                setter='set_%s' % expand_field_selection_name)
            setattr(cls, expand_field_selection_name, selection)

            def on_change_with_selection(self, name=None):
                value = getattr(self, field_name, None)
                if value:
                    return value.__name__
            setattr(cls, 'on_change_with_%s' % expand_field_selection_name,
                on_change_with_selection)

            def on_change_selection(self):
                reference = getattr(self, field_name, None)
                selection = getattr(self, expand_field_selection_name, None)
                if reference:
                    if reference.__name__ == selection:
                        return {}
                return {
                    field_name: '%s,' % selection,
                    }
            setattr(cls, 'on_change_%s' % expand_field_selection_name,
                on_change_selection)

            @classmethod
            def set_selection(cls, records, name, value):
                pass
            setattr(cls, 'set_%s' % expand_field_selection_name, set_selection)
        for i, (target, _) in enumerate(
                getattr(cls, field.selection)()):
            expand_field_name = '%s_%s' % (field_name, i)
            if not getattr(cls, expand_field_name, None):
                expand_field = ReferenceForm(field, target, states={
                        'invisible': (Eval(expand_field_selection_name)
                            != target),
                        },
                    depends=[expand_field_selection_name])
                setattr(cls, expand_field_name, expand_field)

    @staticmethod
    def convert_view(field_name):
        '''
        Decorator to convert view.
        It must be applied on ModelView._view_look_dom_arch
        '''
        def convert(func):
            @wraps(func)
            def _view_look_dom_arch(cls, tree, type, field_children=None):
                found = tree.xpath("//field[@name='%s']" % field_name)
                if found:
                    element_reference = found[0]
                    field = getattr(cls, field_name)

                    selection_name = '%s_selection' % field_name
                    element_selection = copy.copy(element_reference)
                    element_selection.set('name', selection_name)
                    element_reference.addprevious(element_selection)
                    for i in range(len(getattr(cls, field.selection)())):
                        element_form = copy.copy(element_reference)
                        element_form.set('name', '%s_%s' % (field_name, i))
                        element_reference.addprevious(element_form)
                    parent = element_reference.getparent()
                    parent.remove(element_reference)
                result = func(cls, tree, type, field_children=field_children)
                return result
            return _view_look_dom_arch
        return convert

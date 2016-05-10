from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.model import fields as tryton_fields

from trytond.modules.cog_utils import model, fields, utils
from trytond.modules.rule_engine import RuleMixin


__all__ = [
    'ProcessAction',
    ]


class ProcessAction(model.CoopView, RuleMixin):
    __name__ = 'process.action'

    target_path = fields.Char('Target Path',
        states={'invisible': Eval('content', '') != 'rule'},
        depends=['content'], help='A path from the processed object '
        'to the data on which to execute the rule\n\nExample : '
        'for a contract, "object.options" will run the rule on all contract '
        'options')

    @classmethod
    def __setup__(cls):
        super(ProcessAction, cls).__setup__()
        cls.content.selection.append(('rule', 'Rule'))
        cls.rule.required = False
        cls.rule.states = {
            'required': Eval('content', '') == 'rule',
            'invisible': Eval('content', '') != 'rule'}
        cls.rule.depends = ['content']
        cls.rule.domain = [('type_', '=', 'process_check')]
        cls._error_messages.update({
                'bad_target_path':
                'Target path "%s" must start with "object."',
                'invalid_path_field': 'Invalid field "%(field_name)s" for '
                'model %(model_name)s',
                'invalid_path_field_type': 'Invalid field type '
                '"%(field_type)s" for node "%(node)s"',
                })

    @fields.depends('content', 'rule_extra_data', 'target_path')
    def on_change_with_exec_parameters(self, name=None):
        if self.content != 'rule':
            return super(ProcessAction, self).on_change_with_exec_parameters(
                name)
        data = []
        if self.target_path:
            data.append(self.target_path)
        if self.rule_extra_data:
            data.append(unicode(self.rule_extra_data_string))
        return '\n'.join(data)

    @fields.depends('content', 'rule')
    def on_change_with_exec_rec_name(self, name=None):
        if self.content != 'rule':
            return super(ProcessAction, self).on_change_with_exec_rec_name(
                name)
        return self.rule.rec_name if self.rule else ''

    @classmethod
    def validate(cls, instances):
        super(ProcessAction, cls).validate(instances)
        pool = Pool()
        for instance in instances:
            if not instance.target_path:
                continue
            if not instance.target_path.startswith('object.'):
                cls.raise_user_error('bad_target_path',
                    (instance.target_path,))
            cur_model = pool.get(instance.on_model.model)
            for path in instance.target_path.split('.')[1:]:
                cur_field = cur_model._fields.get(path, None)
                if cur_field is None:
                    cls.raise_user_error('invalid_path_field', {
                            'model_name': cur_model.__name__,
                            'field_name': path})
                if isinstance(cur_field, (tryton_fields.Function,
                            tryton_fields.Property)):
                    cur_field = cur_field._field
                if isinstance(cur_field, (tryton_fields.One2Many,
                            tryton_fields.Many2One)):
                    cur_model = pool.get(cur_field.model_name)
                elif isinstance(cur_field, tryton_fields.Many2Many):
                    cur_model = pool.get(
                        pool.get(cur_field.relation_name
                            )._fields[cur_field.target].model_name)
                elif isinstance(cur_field, tryton_fields.Reference):
                    break
                else:
                    cls.raise_user_error('invalid_path_field_type', {
                            'field_type': str(cur_field.__class__.__name__),
                            'node': path,
                            })

    def get_rule_targets(self, target):
        if not self.target_path:
            return [target]
        new_targets = [target]
        for path in self.target_path.split('.')[1:]:
            new_targets = [getattr(x, path) for x in new_targets
                if getattr(x, path)]
            if isinstance(new_targets[0], tuple):
                new_targets = sum(new_targets, ())
        return new_targets

    def execute(self, target):
        if self.content != 'rule':
            return super(ProcessAction, self).execute(target)
        targets = self.get_rule_targets(target)
        for target in targets:
            exec_context = {'date': utils.today()}
            target.init_dict_for_rule_engine(exec_context)
            result = self.rule.execute(exec_context, self.rule_extra_data)
            if result.errors:
                self.raise_user_error('\r\r'.join(result.print_errors()))
            if result.warnings:
                self.raise_user_warning(str((self.id, target)), '\r\r'.join(
                        result.print_warnings()))

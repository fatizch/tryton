# -*- coding:utf-8 -*-
import copy

from trytond import backend
from trytond.pool import PoolMeta
from trytond.rpc import RPC
from trytond.model import DictSchemaMixin
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, coop_string
from trytond.modules.offered.offered import CONFIG_KIND

__metaclass__ = PoolMeta

__all__ = [
    'ExtraData',
    'ExtraDataSubExtraDataRelation',
    ]


class ExtraData(DictSchemaMixin, model.CoopSQL, model.CoopView,
        model.TaggedMixin):
    'Extra Data'

    __name__ = 'extra_data'
    _func_key = 'name'

    with_default_value = fields.Boolean('Default Value')
    default_value_boolean = fields.Function(
        fields.Boolean('Default Value',
            states={
                'required': Bool(Eval('with_default_value')) & (
                    Eval('type_') == 'boolean'),
                'invisible': ~Eval('with_default_value') | (
                    Eval('type_') != 'boolean'),
                },
            depends=['type_', 'with_default_value']),
        'get_default_value', 'set_default_value')
    default_value_selection = fields.Function(
        fields.Selection('get_default_value_selection', 'Default Value',
            states={
                'required': Bool(Eval('with_default_value')) & (
                    Eval('type_') == 'selection'),
                'invisible': ~Eval('with_default_value') | (
                    Eval('type_') != 'selection'),
                },
            depends=['type_', 'selection', 'with_default_value'],
            ),
        'get_default_value', 'set_default_value')
    default_value = fields.Char('Default Value')
    kind = fields.Selection([
            ('', ''),
            ('contract', 'Contract'),
            ('product', 'Product'),
            ('covered_element', 'Covered Element'),
            ('option', 'Option'),
            ('loss', 'Loss'),
            ('benefit', 'Benefit'),
            ], 'Kind', required=True)
    sub_datas = fields.One2Many('extra_data-sub_extra_data', 'master',
        'Sub Data', context={'kind': Eval('extra_data_kind')},
        states={'invisible': Eval('sub_data_config_kind') != 'simple'},
        target_not_required=True)
    sub_data_config_kind = fields.Selection(CONFIG_KIND,
        'Sub Data Config Kind')
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='RESTRICT',
        states={'invisible': Eval('sub_data_config_kind') != 'advanced'})

    @classmethod
    def __register__(cls, module_name):
        super(ExtraData, cls).__register__(module_name)
        # Migration from 1.3: Drop start_date, end_date column
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        extra_data = TableHandler(cursor, cls)
        if extra_data.column_exist('start_date'):
            extra_data.drop_column('start_date')
        if extra_data.column_exist('end_date'):
            extra_data.drop_column('end_date')

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.name.string = 'Code'
        cls.string.string = 'Name'
        cls.type_.selection.insert(0, ('', ''))
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(name)', 'The code must be unique!'),
            ]
        cls.__rpc__.update({'get_default_value_selection': RPC(instantiate=0)})
        cls._error_messages.update({
                'invalid_value': 'Invalid value %s for key %s in field %s of '
                '%s',
                'expected_value': 'Expected key %s to be set in field %s of '
                '%s',
                })

    @classmethod
    def is_master_object(cls):
        return True

    @staticmethod
    def default_type_():
        return ''

    @staticmethod
    def default_kind():
        if 'extra_data_kind' in Transaction().context:
            return Transaction().context['extra_data_kind']
        return ''

    @staticmethod
    def default_default_value_selection():
        return ''

    @staticmethod
    def default_sub_data_config_kind():
        return 'simple'

    @fields.depends('default_value_selection', 'type_', 'selection',
        'with_default_value')
    def on_change_selection(self):
        if self.default_value_selection is None:
            return
        selection = self.get_default_value_selection()
        if self.default_value_selection not in selection:
            self.default_value_selection = selection[0] or None

    @fields.depends('type_')
    def on_change_type_(self):
        if not hasattr(self, 'type_'):
            return
        if self.type_ == 'selection':
            self.selection = ''
            self.default_selection = ''
        elif self.type_ == 'boolean':
            self.default_boolean = False
        else:
            self.default = ''

    @fields.depends('name', 'string')
    def on_change_with_name(self):
        if not self.name and self.string:
            return coop_string.slugify(self.string)
        return self.name

    @fields.depends('tags')
    def on_change_with_tags_name(self, name=None):
        return ', '.join([x.name for x in self.tags])

    @fields.depends('type_', 'selection', 'with_default_value')
    def get_default_value_selection(self):
        selection = [('', '')]
        selection += [x.split(':') for x in self.selection.splitlines()
            if ':' in x] if self.selection else []
        return selection

    def get_default_value(self, name):
        if name is None:
            name_type = self.type_
        else:
            name_type = name[14:]
        if name_type == 'boolean':
            return self.default_value == 'True'
        if name_type == 'selection':
            return self.default_value if self.type_ == 'selection' else None
        return None

    @classmethod
    def set_default_value(cls, schemas, name, value):
        name_type = name[14:]
        for schema in schemas:
            if not name_type == schema.type_:
                continue
            if name_type == 'boolean':
                if isinstance(value, bool) and value:
                    cls.write(schemas, {'default_value': 'True'})
                else:
                    cls.write(schemas, {'default_value': 'False'})
            elif name_type == 'selection':
                cls.write(schemas, {'default_value': value})

    def validate_value(self, value):
        if self.type_ == 'selection':
            if not value:
                return False
            selection = [v.split(':')[0].strip()
                for v in self.selection.splitlines() if v]
            if value not in selection:
                return False
        return True

    @classmethod
    def check_extra_data(cls, instance, field_name):
        field_value = getattr(instance, field_name, None)
        if field_value is None:
            return True, []
        expected_values = getattr(instance, 'on_change_with_%s' % field_name,
            None)
        if expected_values is not None:
            expected_values = expected_values()
        res, errs = True, []
        for k, v in field_value.iteritems():
            if expected_values is not None:
                if k in expected_values:
                    del expected_values[k]
                else:
                    continue
            key, = cls.search([('name', '=', k)])
            if not key.validate_value(v):
                res = False
                cls.append_functional_error('invalid_value', (v, k, field_name,
                        instance.get_rec_name(None)))
        if expected_values is not None:
            for k, v in expected_values.iteritems():
                # This is a serious error, as the user should have no way to
                # manage it on his own
                cls.raise_user_error('expected_value', (k, field_name,
                        instance.get_rec_name(None)))
        return res, errs

    @classmethod
    def calculate_value_set(cls, possible_schemas, all_schemas, values):
        working_value_set = copy.copy(values)
        childs = set([])
        for schema in all_schemas:
            for sub_data in schema.sub_datas:
                if sub_data.child not in all_schemas:
                    continue
                childs.add(sub_data.child)
        tree_top = [schema for schema in all_schemas if schema not in childs]
        forced_values = {}
        non_forced_values = {}
        for schema in tree_top:
            new_vals = {}
            schema.update_field_value(new_vals, working_value_set, all_schemas)
            forced_values.update(
                dict([(x, y[0]) for x, y in new_vals.items() if y[1]]))
            non_forced_values.update(
                dict([(x, y[0]) for x, y in new_vals.items() if not y[1]]))
        res = {}
        res.update(non_forced_values)
        res.update(forced_values)
        return dict([
            (k.name, res[k.name])
            for k in possible_schemas if k.name in res])

    def update_field_value(self, new_vals, init_dict, valid_schemas):
        try:
            cur_value = init_dict[self.name]
        except KeyError:
            cur_value = (self.get_default_value(None)
                if self.with_default_value else None)
        # We set a boolean to know if the value is forced through rule engine
        new_vals[self.name] = (cur_value, False)
        args = {'extra_data': init_dict}
        if self.sub_data_config_kind == 'advanced' and self.rule:
            rule_engine_result = self.rule.execute(args)
            if (not rule_engine_result.errors
                    and type(rule_engine_result.result) is dict):
                for key, value in rule_engine_result.result.items():
                    new_vals[key] = (value, True)
        elif self.sub_data_config_kind == 'simple':
            for sub_data in self.sub_datas:
                if sub_data.child not in valid_schemas:
                    continue
                sub_data.update_if_needed(
                    new_vals, cur_value, init_dict, valid_schemas)

    def get_value_as_string(self, value, lang=None):
        if self.type_ == 'selection' and value:
            cur_dict = dict(self.__class__.get_keys([self])[0]['selection'])
            return cur_dict[value]
        elif self.type_ in ['integer', 'float', 'numeric'] and not value:
            return '0'
        elif self.type_ == 'boolean':
            return coop_string.translate_bool(value, lang)
        if not value:
            return ''
        return str(value)

    @classmethod
    def get_extra_data_definitions(cls, instance, field_name, type_, date):
        all_schemas = set(getattr(instance, field_name))
        possible_schemas = set([x for x in all_schemas
                if x.kind == type_])
        return all_schemas, possible_schemas

    @classmethod
    def get_extra_data_summary(cls, instances, var_name, lang=None):
        res = {}
        domain = []
        keys = []
        for instance in instances:
            keys += [key for key in getattr(instance, var_name).iterkeys()]
        domain = [[('name', '=', key)] for key in set(keys)]
        domain.insert(0, 'OR')
        compl_dict = dict([x.name, x] for x in cls.search(domain))
        for instance in instances:
            res[instance.id] = ''
            for key, value in getattr(instance, var_name).iteritems():
                res[instance.id] += u'\n%s : %s' % (
                    coop_string.translate_value(compl_dict[key], 'string',
                        lang),
                    compl_dict[key].get_value_as_string(value, lang))
            res[instance.id] = coop_string.re_indent_text(res[instance.id], 1)
        return res

    @classmethod
    def get_extra_data_value(cls, instance, key, at_date=None):
        extra_data = instance.get_all_extra_data(at_date)
        res = extra_data.get(key)
        if res is not None:
            return res
        # TODO : To Enhance and load data_def in cache
        data_def, = cls.search([('name', '=', key)])
        if data_def.type_ in ['integer', 'float', 'numeric']:
            return 0
        elif data_def.type_ in ['char', 'selection']:
            return ''

    @classmethod
    def search_tags(cls, name, clause):
        return [('tags.name',) + tuple(clause[1:])]

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['name', 'string', 'type_', 'selection_json']


class ExtraDataSubExtraDataRelation(model.CoopSQL, model.CoopView):
    'Extra Data to Sub Extra Data Relation'

    __name__ = 'extra_data-sub_extra_data'

    master = fields.Many2One(
        'extra_data', 'Master', ondelete='CASCADE')
    child = fields.Many2One(
        'extra_data', 'Child', ondelete='RESTRICT')
    select_value = fields.Char('Select value')

    def does_match(self, value):
        if not (hasattr(self, 'select_value') and self.select_value):
            return True
        return str(value) in (self.select_value.replace(' ', '').split(','))

    def update_if_needed(self, new_values, value, value_dict, valid_schemas):
        if not self.does_match(value):
            return
        self.child.update_field_value(new_values, value_dict, valid_schemas)

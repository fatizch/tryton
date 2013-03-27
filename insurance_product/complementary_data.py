#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool
from trytond.model import DictSchemaMixin
from trytond.pyson import Eval, Bool, Or, Not
from trytond.transaction import Transaction

from trytond.modules.coop_utils import fields, model, utils, coop_string


__all__ = [
    'ComplementaryDataRecursiveRelation',
    'ComplementaryDataDefinition',
]


class ComplementaryDataRecursiveRelation(model.CoopSQL, model.CoopView):
    'Complementary Data recursive relation'

    __name__ = 'ins_product.complementary_data_recursive_relation'

    master = fields.Many2One(
        'ins_product.complementary_data_def', 'Master', ondelete='CASCADE')
    child = fields.Many2One(
        'ins_product.complementary_data_def', 'Child', ondelete='RESTRICT')
    select_value = fields.Char('Select value')

    def does_match(self, value):
        if not (hasattr(self, 'select_value') and self.select_value):
            return True
        return str(value) in (self.select_value.replace(' ', '').split(','))

    def update_if_needed(self, new_values, value, value_dict, valid_schemas):
        if not self.does_match(value):
            return
        self.child.update_field_value(new_values, value_dict, valid_schemas)


class ComplementaryDataDefinition(
        DictSchemaMixin, model.CoopSQL, model.CoopView):
    'Complementary Data Definition'

    __name__ = 'ins_product.complementary_data_def'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    with_default_value = fields.Boolean('Default Value')
    default_value_boolean = fields.Function(
        fields.Boolean('Default Value'),
        'get_default_value', 'set_default_value')
    default_value_char = fields.Function(
        fields.Char('Default Value'),
        'get_default_value', 'set_default_value')
    default_value_selection = fields.Function(
        fields.Char('Default Value'),
        'get_default_value', 'set_default_value')
    default_value = fields.Char('Default Value')
    is_shared = fields.Function(fields.Boolean('Shared'), 'get_is_shared')
    kind = fields.Selection(
        [
            ('contract', 'Contract'),
            ('product', 'Product'),
            ('sub_elem', 'Sub Element'),
            ('loss', 'Loss'),
            ('benefit', 'Benefit'),
            ('rule_engine', 'Rule Engine'),
        ],
        'Kind')
    sub_datas = fields.One2Many(
        'ins_product.complementary_data_recursive_relation',
        'master', 'Sub Data', context={
            'kind': Eval('complementary_data_kind')})

    @classmethod
    def __setup__(cls):
        super(ComplementaryDataDefinition, cls).__setup__()

        def update_field(field_name, field):
            if not hasattr(field, 'states'):
                field.states = {}
            field.states['invisible'] = Or(
                Eval('type_') != field_name[14:],
                ~Bool(Eval('with_default_value')))
            if field_name[14:] == 'selection':
                field.states['required'] = Not(field.states['invisible'])

        map(lambda x: update_field(x[0], x[1]),
            [(elem, getattr(cls, elem)) for elem in dir(cls) if
                elem.startswith('default_value_')])

        cls.type_ = copy.copy(cls.type_)
        utils.remove_tuple_from_list(cls.type_.selection, 'sha')
        utils.remove_tuple_from_list(cls.type_.selection, 'datetime')
        utils.remove_tuple_from_list(cls.type_.selection, 'float')
        utils.remove_tuple_from_list(cls.type_.selection, 'timestamp')
        utils.remove_tuple_from_list(cls.type_.selection, 'time')
        utils.remove_tuple_from_list(cls.type_.selection, 'binary')

        cls.name = copy.copy(cls.name)
        if not cls.name.on_change_with:
            cls.name.on_change_with = []
        cls.name.on_change_with.append('string')
        cls.name.on_change_with.append('name')
        cls.name.string = 'Code'

        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(name)', 'The code must be unique!'),
        ]

    @staticmethod
    def default_start_date():
        return utils.today()

    def get_is_shared(self, name):
        return False

    def get_default_value(self, name):
        if name is None:
            name_type = self.type_
        else:
            name_type = name[14:]
        if name_type == 'boolean':
            return self.default_value == 'True'
        if name_type == 'char' or name_type == 'selection':
            return self.default_value
        return None

    @classmethod
    def set_default_value(cls, schemas, name, value):
        name_type = name[14:]
        if name_type == 'boolean':
            if value:
                cls.write(schemas, {'default_value': 'True'})
            else:
                cls.write(schemas, {'default_value': 'False'})
        elif name_type == 'char' or name_type == 'selection':
            cls.write(schemas, {'default_value': value})

    # Should be Deprecated, as the search part of the dict widget is removed
    # Also remove the give_me functions which use dd_args
    @classmethod
    def _search(
            cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        # Important : if you do not check (and set below) relation_selection,
        # There is a risk of infinite recursion if your code needs to do a
        # search (might only be a O2M / M2M)
        if not('relation_selection' in Transaction().context) and \
                'for_product' in Transaction().context and \
                'at_date' in Transaction().context and \
                'dd_args' in Transaction().context:
            for_product = Transaction().context['for_product']
            at_date = Transaction().context['at_date']
            dd_args = Transaction().context['dd_args']
            if for_product and at_date:
                the_product, = Pool().get('ins_product.product').search(
                    [('id', '=', Transaction().context['for_product'])])
                with Transaction().set_context({'relation_selection': True}):
                    good_schemas = the_product.get_result(
                        'complementary_data_getter',
                        {
                            'date': Transaction().context['at_date'],
                            'dd_args': dd_args
                        })
                domain.append(('id', 'in', good_schemas[0]))
        return super(ComplementaryDataDefinition, cls).search(
            domain, offset=offset, limit=limit, order=order, count=count,
            query_string=query_string)

    def valid_at_date(self, at_date):
        if at_date and hasattr(self, 'start_date') and self.start_date:
            if self.start_date > at_date:
                return False
        if at_date and hasattr(self, 'end_date') and self.end_date:
            if self.end_date < at_date:
                return False
        return True

    @staticmethod
    def default_kind():
        if 'complementary_data_kind' in Transaction().context:
            return Transaction().context['complementary_data_kind']
        return 'contract'

    def on_change_with_name(self):
        if not self.name and self.string:
            return coop_string.remove_blank_and_invalid_char(self.string)
        return self.name

    @classmethod
    def calculate_value_set(cls, possible_schemas, all_schemas, values):
        working_value_set = copy.copy(values)
        childs = set([])
        for schema in all_schemas:
            for sub_data in schema.sub_datas:
                if not sub_data.child in all_schemas:
                    continue
                childs.add(sub_data.child)
        tree_top = [schema for schema in all_schemas if not schema in childs]
        new_vals = {}
        for schema in tree_top:
            schema.update_field_value(new_vals, working_value_set, all_schemas)
        return dict([
            (k.name, new_vals[k.name])
            for k in possible_schemas if k.name in new_vals])

    def update_field_value(self, new_vals, init_dict, valid_schemas):
        try:
            cur_value = init_dict[self.name]
        except KeyError:
            cur_value = self.get_default_value(None)
        new_vals[self.name] = cur_value
        for sub_data in self.sub_datas:
            if not sub_data.child in valid_schemas:
                continue
            sub_data.update_if_needed(
                new_vals, cur_value, init_dict, valid_schemas)

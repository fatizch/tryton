#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pool import Pool
from trytond.ir.model import SchemaElementMixin
from trytond.pyson import Eval, Bool, Or, Not
from trytond.transaction import Transaction
try:
    import simplejson as json
except ImportError:
    import json

from trytond.modules.coop_utils import model, utils


__all__ = [
    'CoopSchemaElement',
    'SchemaElementRelation',
    'DynamicDataManager',
    ]


class CoopSchemaElement(SchemaElementMixin, model.CoopSQL, model.CoopView):
    'Dynamic Data Definition'

    __name__ = 'ins_product.schema_element'

    manager = fields.Many2One(
        'ins_product.dynamic_data_manager',
        'Manager',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    with_default_value = fields.Boolean('Default Value')
    default_value_boolean = fields.Function(fields.Boolean(
        'Default Value'),
        'get_default_value',
        'set_default_value')
    default_value_char = fields.Function(fields.Char(
        'Default Value'),
        'get_default_value',
        'set_default_value')
    default_value_selection = fields.Function(fields.Char(
        'Default Value'),
        'get_default_value',
        'set_default_value')
    default_value = fields.Char('Default Value')
    is_shared = fields.Function(fields.Boolean('Shared'), 'get_is_shared')

    @classmethod
    def __setup__(cls):
        super(CoopSchemaElement, cls).__setup__()

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
        utils.remove_tuple_from_list(cls.type_.selection, 'numeric')
        utils.remove_tuple_from_list(cls.type_.selection, 'timestamp')
        utils.remove_tuple_from_list(cls.type_.selection, 'time')
        utils.remove_tuple_from_list(cls.type_.selection, 'binary')

    @staticmethod
    def default_start_date():
        return utils.today()

    def get_is_shared(self, name):
        return self.id and not self.manager is None

    def get_default_value(self, name):
        if name is None:
            name_type = self.type_
        else:
            name_type = name[14:]
        if name_type == 'boolean':
            return self.default_value == 'True'
        if name_type == 'char' or name_type == 'selection':
            return self.default_value

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

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
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
                        'dynamic_data_getter',
                        {'date': Transaction().context['at_date'],
                         'dd_args': dd_args})
                domain.append(('id', 'in', good_schemas[0]))
        return super(CoopSchemaElement, cls).search(domain, offset=offset,
                limit=limit, order=order, count=count,
                query_string=query_string)

    @classmethod
    def describe_keys(cls, key_ids):
        keys = []
        for key in cls.browse(key_ids):
            with Transaction().set_context(language='fr_FR'):
                english_key = cls(key.id)
                choices = dict(json.loads(english_key.choices or '[]'))
            choices.update(dict(json.loads(key.choices or '[]')))
            new_key = {
                'name': key.name,
                'technical_name': key.technical_name,
                'type_': key.type_,
                'choices': choices.items(),
            }
            keys.append(new_key)
        return keys

    def valid_at_date(self, at_date):
        if hasattr(self, 'start_date') and self.start_date:
            if self.start_date > at_date:
                return False
        if hasattr(self, 'end_date') and self.end_date:
            if self.end_date < at_date:
                return False
        return True


class SchemaElementRelation(model.CoopSQL):
    'Relation between schema element and dynamic data manager'

    __name__ = 'ins_product.schema_element_relation'

    the_manager = fields.Many2One('ins_product.dynamic_data_manager',
        'Manager', select=1, required=True, ondelete='CASCADE')
    schema_element = fields.Many2One('ins_product.schema_element',
        'Schema Element', select=1, required=True, ondelete='RESTRICT')


class DynamicDataManager(model.CoopSQL, model.CoopView):
    'Dynamic Data Manager'

    __name__ = 'ins_product.dynamic_data_manager'

    master = fields.Reference(
        'Product',
        selection=[
            ('ins_product.product', 'Product'),
            ('ins_product.coverage', 'Coverage')])

    specific_dynamic = fields.One2Many(
        'ins_product.schema_element',
        'manager',
        'Specific Dynamic Data')
    shared_dynamic = fields.Many2Many(
        'ins_product.schema_element_relation',
        'the_manager',
        'schema_element',
        'Shared Dynamic Data',
        domain=[('manager', '=', None)],
        # Not needed but allows to force the display for O2MDomain validation
        depends=['kind'])
    kind = fields.Selection([
        ('main', 'Main'),
        ('sub_elem', 'Sub Element')],
        'Kind')

    def get_valid_schemas_ids(self, date):
        return map(lambda x: x.id, self.get_valid_schemas(date))

    def get_valid_schemas(self, date):
        res = []
        for elem in self.specific_dynamic:
            if elem.valid_at_date(date):
                res.append(elem)
        for elem in self.shared_dynamic:
            if elem.valid_at_date(date):
                res.append(elem)
        return res

    @staticmethod
    def default_kind():
        if not 'for_kind' in Transaction().context:
            return 'main'
        return Transaction().context['for_kind']

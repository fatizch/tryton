#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.model import DictSchemaMixin
from trytond.pyson import Eval, Bool, Or
from trytond.transaction import Transaction

from trytond.modules.coop_utils import fields, model, utils, coop_string
from trytond.modules.offered.offered import CONFIG_KIND

__metaclass__ = PoolMeta

__all__ = [
    'ComplementaryDataDefinition',
    'ComplementaryDataRecursiveRelation',
    'Tag',
    'ComplementaryDataDefTagRelation',
    ]


class ComplementaryDataDefinition(
        DictSchemaMixin, model.CoopSQL, model.CoopView):
    'Complementary Data Definition'

    __name__ = 'extra_data'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    with_default_value = fields.Boolean('Default Value')
    default_value_boolean = fields.Function(
        fields.Boolean('Default Value'),
        'get_default_value', 'set_default_value')
    default_value_selection = fields.Function(
        fields.Selection('get_default_value_selection', 'Default Value',
            selection_change_with=['type_', 'selection', 'with_default_value'],
            depends=['type_', 'selection', 'with_default_value']),
        'get_default_value', 'set_default_value')
    default_value = fields.Char('Default Value')
    kind = fields.Selection(
        [
            ('contract', 'Contract'),
            ('product', 'Product'),
            ('sub_elem', 'Covered Element'),
            ('loss', 'Loss'),
            ('benefit', 'Benefit'),
            ('rule_engine', 'Rule Engine'),
        ],
        'Kind')
    sub_datas = fields.One2Many(
        'extra_data-sub_extra_data',
        'master', 'Sub Data', context={
            'kind': Eval('complementary_data_kind')},
        states={'invisible': Eval('sub_data_config_kind') != 'simple'})
    sub_data_config_kind = fields.Selection(CONFIG_KIND,
        'Sub Data Config Kind')
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='RESTRICT',
        states={'invisible': Eval('sub_data_config_kind') != 'advanced'})
    tags = fields.Many2Many('extra_data-tag', 'compl_data_def',
        'tag', 'Tags')
    tags_name = fields.Function(
        fields.Char('Tags', on_change_with=['tags']),
        'on_change_with_tags_name', searcher='search_tags')

    @classmethod
    def __setup__(cls):
        super(ComplementaryDataDefinition, cls).__setup__()

        def update_field(field_name, field):
            if not hasattr(field, 'states'):
                field.states = {}
            field.states['invisible'] = Or(
                Eval('type_') != field_name[14:],
                ~Bool(Eval('with_default_value')))

        map(lambda x: update_field(x[0], x[1]),
            [(elem, getattr(cls, elem)) for elem in dir(cls) if
                elem.startswith('default_value_')])

        cls.name = copy.copy(cls.name)
        if not cls.name.on_change_with:
            cls.name.on_change_with = []
        cls.name.on_change_with.append('string')
        cls.name.on_change_with.append('name')
        cls.name.string = 'Code'

        cls.type_ = copy.copy(cls.type_)
        if not cls.type_.on_change:
            cls.type_.on_change = []
        cls.type_.on_change.append('type_')

        cls.selection = copy.copy(cls.selection)
        if not cls.selection.on_change:
            cls.selection.on_change = []
        cls.selection.on_change += ['selection', 'default_value_selection']
        cls.selection.states['required'] = (Eval('type_') == 'selection'
            and ~~Eval('with_default_value'))

        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(name)', 'The code must be unique!'),
        ]
        cls.__rpc__.update({'get_default_value_selection': RPC(instantiate=0)})

    @staticmethod
    def default_start_date():
        return utils.today()

    def on_change_type_(self):
        res = {}
        if not hasattr(self, 'type_'):
            return {}
        if self.type_ == 'selection':
            res['selection'] = ''
            res['default_selection'] = ''
        elif self.type_ == 'boolean':
            res['default_boolean'] = False
        else:
            res['default'] = ''
        return res

    def on_change_selection(self):
        if not (hasattr(self, 'default_value_selection') and
                self.default_value_selection):
            return {}
        if not (hasattr(self, 'selection') and self.selection):
            return {'default_value_selection': ''}
        db_selection = self.selection
        selection = [v.split(':')[0].strip()
            for v in db_selection.splitlines() if v]
        if not self.default_value_selection in selection:
            return {'default_value_selection': selection[0] or None}
        return {}

    def get_default_value_selection(self):
        if not (hasattr(self, 'type_') and self.type_ == 'selection'):
            return [('', '')]
        if not (hasattr(self, 'selection') and self.selection):
            return [('', '')]
        res = [x.split(':') for x in self.selection.split('\n')]
        if not (hasattr(self, 'with_default_value')
                and self.with_default_value):
            res.append(('', ''))
        return res

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

    # Should be Deprecated, as the search part of the dict widget is removed
    # Also remove the give_me functions which use dd_args
    @classmethod
    def _search(
            cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
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
                the_product, = Pool().get('offered.product').search(
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
            query=query)

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
    def calculate_value_set(cls, possible_schemas, all_schemas, values, args):
        working_value_set = copy.copy(values)
        childs = set([])
        for schema in all_schemas:
            for sub_data in schema.sub_datas:
                if not sub_data.child in all_schemas:
                    continue
                childs.add(sub_data.child)
        tree_top = [schema for schema in all_schemas if not schema in childs]
        forced_values = {}
        non_forced_values = {}
        for schema in tree_top:
            new_vals = {}
            schema.update_field_value(new_vals, working_value_set, all_schemas,
                args)
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

    def update_field_value(self, new_vals, init_dict, valid_schemas, args):
        try:
            cur_value = init_dict[self.name]
        except KeyError:
            cur_value = self.get_default_value(None)
        # We set a boolean to know if the value is forced through rule engine
        new_vals[self.name] = (cur_value, False)
        if self.sub_data_config_kind == 'advanced' and self.rule:
            rule_engine_result = self.rule.execute(args)
            if (not rule_engine_result.errors
                    and type(rule_engine_result.result) is dict):
                for key, value in rule_engine_result.result.items():
                    new_vals[key] = (value, True)
        elif self.sub_data_config_kind == 'simple':
            for sub_data in self.sub_datas:
                if not sub_data.child in valid_schemas:
                    continue
                sub_data.update_if_needed(
                    new_vals, cur_value, init_dict, valid_schemas, args)

    def get_value_as_string(self, value, lang=None):
        if self.type_ == 'selection':
            cur_dict = dict(self.__class__.get_keys([self])[0]['selection'])
            return cur_dict[value]
        elif self.type_ in ['integer', 'float', 'numeric'] and not value:
            return '0'
        elif self.type_ == 'boolean':
            return coop_string.translate_bool(value, lang)
        return str(value)

    @classmethod
    def get_complementary_data_summary(cls, instances, var_name, lang=None):
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
    def get_complementary_data_value(cls, instance, key, at_date=None):
        compl_data = instance.get_all_complementary_data(at_date)
        res = compl_data.get(key)
        if res:
            return res
        #TODO : To Enhance and load data_def in cache
        data_def, = cls.search([('name', '=', key)])
        if data_def.type_ in ['integer', 'float', 'numeric']:
            return 0
        elif data_def.type_ in ['char', 'selection']:
            return ''

    @staticmethod
    def default_sub_data_config_kind():
        return 'simple'

    def on_change_with_tags_name(self, name=None):
        return ', '.join([x.name for x in self.tags])

    @classmethod
    def search_tags(cls, name, clause):
        return [('tags.name',) + tuple(clause[1:])]

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['name', 'string', 'type_', 'selection_json']


class ComplementaryDataRecursiveRelation(model.CoopSQL, model.CoopView):
    'Complementary Data recursive relation'

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

    def update_if_needed(self, new_values, value, value_dict, valid_schemas,
            args):
        if not self.does_match(value):
            return
        self.child.update_field_value(new_values, value_dict, valid_schemas,
            args)


class Tag():
    'Tag'

    __name__ = 'tag'

    compl_data_defs = fields.Many2Many('extra_data-tag', 'tag',
        'compl_data_def', 'Complementary Data')

    @classmethod
    def _export_skips(cls):
        result = super(Tag, cls)._export_skips()
        result.add('compl_data_defs')
        return result


class ComplementaryDataDefTagRelation(model.CoopSQL):
    'Relation between complementary data def and tag'

    __name__ = 'extra_data-tag'

    compl_data_def = fields.Many2One('extra_data',
        'Complementary Data Def', ondelete='CASCADE')
    tag = fields.Many2One('tag', 'Tag', ondelete='RESTRICT')

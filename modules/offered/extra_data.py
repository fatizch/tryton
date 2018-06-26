# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import Pool
from trytond.cache import Cache
from trytond.rpc import RPC
from trytond.model import DictSchemaMixin, Unique, Model
from trytond.model.fields.dict import TranslatedDict
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, model, coog_string


__all__ = [
    'ExtraData',
    'ExtraDataSubExtraDataRelation',
    ]


class ExtraData(DictSchemaMixin, model.CoogSQL, model.CoogView,
        model.TaggedMixin):
    'Extra Data'

    __name__ = 'extra_data'
    _func_key = 'name'

    has_default_value = fields.Boolean('Default Value')
    default_value_boolean = fields.Function(
        fields.Boolean('Default Value',
            states={
                'invisible': ~Eval('has_default_value') | (
                    Eval('type_') != 'boolean'),
                },
            depends=['type_', 'has_default_value']),
        'get_default_value', 'setter_void')
    default_value_selection = fields.Function(
        fields.Selection('get_default_value_selection', 'Default Value',
            states={
                'required': Bool(Eval('has_default_value')) & (
                    Eval('type_') == 'selection'),
                'invisible': ~Eval('has_default_value') | (
                    Eval('type_') != 'selection'),
                },
            depends=['type_', 'selection', 'has_default_value'],
            ),
        'get_default_value', 'setter_void')
    default_value = fields.Char('Default Value', states={'invisible': True})
    kind = fields.Selection([
            ('', ''),
            ('contract', 'Contract'),
            ('product', 'Product'),
            ('package', 'Package'),
            ('covered_element', 'Covered Element'),
            ('option', 'Option'),
            ('loss', 'Loss'),
            ('benefit', 'Benefit'),
            ], 'Kind', required=True)
    sub_datas = fields.One2Many('extra_data-sub_extra_data', 'master',
        'Sub Data', context={'kind': Eval('kind')},
        target_not_required=True)
    parents = fields.Many2Many('extra_data-sub_extra_data', 'child', 'master',
        'Parents', states={'readonly': True})
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='RESTRICT')

    _translation_cache = Cache('_get_extra_data_summary_cache')
    _extra_data_cache = Cache('extra_data_cache')
    _extra_data_structure_cache = Cache('extra_data_structure')

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.name.string = 'Code'
        cls.string.string = 'Name'
        cls.type_.selection.insert(0, ('', ''))
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.name), 'The code must be unique!'),
            ]
        cls.__rpc__.update({'get_default_value_selection': RPC(instantiate=0)})
        cls._error_messages.update({
                'invalid_value': 'Invalid value for key %s in field %s of %s',
                'expected_value': 'Expected key %s to be set in field %s of '
                '%s',
                'too_many_recursion_levels': 'Too many recursion levels in "'
                'sub data definition',
                'missing_sub_data_def': 'Data %(sub_data)s is missing from '
                'the configuration',
                'multiple_parents_matches': 'Data %(data)s has multiple '
                'parents with the current configuration',
                })
        cls._order = [('kind', 'ASC'), ('string', 'ASC')]
        cls._extra_data_providers = getattr(cls, '_extra_data_providers', {})

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.10: Rename with_default_value
        TableHandler = backend.get('TableHandler')
        extra_data = TableHandler(cls)
        if extra_data.column_exist('with_default_value'):
            extra_data.column_rename('with_default_value',
            'has_default_value')

        super(ExtraData, cls).__register__(module_name)

        # migration from a fix in 2.0 due to missing reset of default_value
        cursor = Transaction().connection.cursor()
        cursor.execute("update extra_data "
            "set default_value = Null, selection = Null "
            "where type_ not in ('boolean', 'selection')")

    @classmethod
    def create(cls, vlist):
        created = super(ExtraData, cls).create(vlist)
        cls._extra_data_cache.clear()
        cls._translation_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(ExtraData, cls).delete(ids)
        cls._extra_data_cache.clear()
        cls._translation_cache.clear()

    @classmethod
    def write(cls, *args):
        super(ExtraData, cls).write(*args)
        cls._extra_data_cache.clear()
        cls._translation_cache.clear()

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

    @fields.depends('default_value_selection', 'type_', 'selection',
        'has_default_value')
    def on_change_selection(self):
        if self.default_value_selection is None:
            return
        selection = self.get_default_value_selection()
        if self.default_value_selection not in selection:
            self.default_value_selection = selection[0] or None

    @fields.depends('default_value_selection', 'type_', 'selection',
        'has_default_value')
    def on_change_has_default_value(self):
        if self.has_default_value is True:
            self.default_value_selection = None

    @fields.depends('type_')
    def on_change_type_(self):
        if not hasattr(self, 'type_'):
            return
        if self.type_ == 'selection':
            self.default_selection = ''
        elif self.type_ == 'boolean':
            self.default_boolean = False
        self.default_value = ''
        self.selection = ''

    @fields.depends('name', 'string')
    def on_change_with_name(self):
        if not self.name and self.string:
            return coog_string.slugify(self.string)
        return self.name

    @fields.depends('tags')
    def on_change_with_tags_name(self, name=None):
        return ', '.join([x.name for x in self.tags])

    @fields.depends('default_value_boolean', 'default_value')
    def on_change_default_value_boolean(self):
        self.default_value = str(self.default_value_boolean)

    @fields.depends('default_value_selection', 'default_value')
    def on_change_default_value_selection(self):
        self.default_value = self.default_value_selection

    @fields.depends('type_', 'selection', 'has_default_value')
    def get_default_value_selection(self):
        selection = [('', '')]
        selection += [x.split(':') for x in self.selection.splitlines()
            if ':' in x] if self.selection else []
        return selection

    @classmethod
    def search_tags(cls, name, clause):
        return [('tags.name',) + tuple(clause[1:])]

    def get_default_value(self, name):
        if name is None:
            name_type = self.type_
        else:
            name_type = name[14:]
        if name_type == 'boolean':
            return self.default_value == 'True'
        if name_type == 'selection':
            return self.default_value if self.type_ == 'selection' and \
                self.has_default_value else None
        return None

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
            return
        expected_values = getattr(instance, 'on_change_with_%s' % field_name,
            None)
        if expected_values is not None:
            expected_values = expected_values()
        translated_keys = TranslatedDict(name=field_name, type_='keys')
        trans_keys = translated_keys.__get__(instance,
            instance.__class__)
        for k, v in field_value.items():
            if expected_values is not None:
                if k in expected_values:
                    del expected_values[k]
                else:
                    continue
            key, = cls.search([('name', '=', k)])
            if not key.validate_value(v):
                cls.append_functional_error('invalid_value', (trans_keys[k],
                        coog_string.translate_label(instance, field_name),
                        instance.get_rec_name(None)))
        if expected_values is not None:
            for k, v in expected_values.iteritems():
                # This is a serious error, as the user should have no way to
                # manage it on his own
                cls.raise_user_error('expected_value', (k, field_name,
                        instance.get_rec_name(None)))

    @classmethod
    def get_extra_data_summary(cls, instances, var_name, lang=None):
        res = {}
        for instance in instances:
            vals = []
            for key, value in (getattr(instance, var_name) or {}).iteritems():
                cached_value = cls._translation_cache.get((key, value), None)
                if cached_value is not None:
                    vals.append(cached_value)
                    continue
                translated_vals = TranslatedDict(name=var_name, type_='values')
                translated_keys = TranslatedDict(name=var_name, type_='keys')
                trans_vals = translated_vals.__get__(instance,
                    instance.__class__)
                trans_keys = translated_keys.__get__(instance,
                    instance.__class__)
                vals = []
                for k, v in getattr(instance, var_name).iteritems():
                    if type(v) == bool:
                        vals.append((trans_keys[k], coog_string.translate_bool(
                                    v, lang)))
                    else:
                        vals.append((trans_keys[k], trans_vals[k]))
                    cls._translation_cache.set((k, v), vals[-1])
                break
            res[instance.id] = '\n'.join(('%s : %s' % (x, y) for x, y in vals))
        return res

    @classmethod
    def _register_extra_data_provider(cls, klass, finder, kinds):
        for kind in kinds:
            if kind not in cls._extra_data_providers:
                cls._extra_data_providers[kind] = {}
            data = cls._extra_data_providers[kind]
            if klass.__name__ not in data:
                data[klass.__name__] = set()
            data[klass.__name__].add(finder)

    @classmethod
    def _check_extra_data_def_consistency(cls, given_set):
        def check_children(parent, found, depth):
            if depth == 0:
                cls.raise_user_error('too_many_recursion_levels')
            if parent.name not in found:
                cls.raise_user_error('missing_sub_data_def',
                    {'sub_data': parent.string})
            if len({x.name for x in parent.parents} & found) > 1:
                cls.raise_user_error('multiple_parents_matches',
                    {'data': parent.string})
            for key in parent.sub_datas:
                check_children(key.child, found, depth - 1)

        found = {x.name for x in given_set}
        for elem in given_set:
            check_children(elem, found, 5)

    @classmethod
    def _global_extra_data_structure(cls, kind):
        cache = Pool().get('extra_data')._extra_data_structure_cache
        cached = cache.get('kind:%s' % kind, -1)
        if cached != -1:
            return cached

        all_keys = cls.search([('kind', '=', kind)])
        bases = {x.name: x._get_structure() for x in all_keys
            if not any([y for y in all_keys if y in x.parents])}

        cache.set('kind:%s' % kind, bases)
        return bases

    def _get_structure(self):
        base = self.get_keys([self])[0]
        res = {
            'code': self.name,
            'name': self.string,
            'technical_kind': self.type_,
            'business_kind': self.kind,
            }

        if self.has_default_value:
            res['default'] = self.default_value

        # Rely on tryton for translations, etc...
        for key in ('selection', 'sorted', 'digits'):
            if key in base:
                res[key] = base[key]

        if not self.sub_datas:
            return res

        res['sub_data'] = []
        for sub_data in self.sub_datas:
            res['sub_data'].append(('=', sub_data.select_value,
                    sub_data.child._get_structure()))

        return res

    @classmethod
    def _refresh_extra_data(cls, base_data, structure):
        new_data = {}
        for key, value in base_data.iteritems():
            if key not in structure:
                continue
            new_data[key] = value
            sub_datas = structure[key].get('sub_data', [])
            for operator, match_value, sub_data in sub_datas:
                if cls._sub_data_matches(match_value, operator, value):
                    if sub_data['code'] in base_data:
                        sub_base = {
                            sub_data['code']: base_data[sub_data['code']]}
                    else:
                        sub_base = cls._sub_data_init(sub_data)
                    new_data.update(cls._refresh_extra_data(sub_base,
                            {sub_data['code']: sub_data}))
        # Add root values which are not already in the data
        for key, value in structure.iteritems():
            if key in new_data:
                continue
            base = cls._sub_data_init(value)
            new_data.update(cls._refresh_extra_data(base, {key: value}))
        return new_data

    @classmethod
    def _sub_data_matches(cls, match_value, operator, value):
        if operator == '=':
            return match_value == value
        raise NotImplementedError

    @classmethod
    def _sub_data_init(cls, data):
        if not data.get('default', None):
            return {data['code']: None}
        if data['technical_kind'] in ('char', 'selection'):
            return {data['code']: data['default']}
        elif data['technical_kind'] == 'boolean':
            return {data['code']: bool(data['default'])}
        raise NotImplementedError

    @classmethod
    def _extra_data_struct(cls, name):
        value = cls._extra_data_cache.get(name, -1)
        if value != -1:
            return value
        instance = cls.search([('name', '=', name)])[0]
        instance_data = instance._extra_data_struct_extract()
        cls._extra_data_cache.set(name, instance_data)
        return instance_data.copy()

    def _extra_data_struct_extract(self):
        return {
            'type_': self.type_,
            'kind': self.kind,
            'id': self.id,
            }


class ExtraDataSubExtraDataRelation(model.CoogSQL, model.CoogView):
    'Extra Data to Sub Extra Data Relation'

    __name__ = 'extra_data-sub_extra_data'

    master = fields.Many2One('extra_data', 'Master', ondelete='CASCADE',
        select=True)
    child = fields.Many2One('extra_data', 'Child', ondelete='RESTRICT')
    select_value = fields.Char('Select value')

    @classmethod
    def create(cls, vlist):
        created = super(ExtraDataSubExtraDataRelation, cls).create(vlist)
        Pool().get('extra_data')._extra_data_structure_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(ExtraDataSubExtraDataRelation, cls).delete(ids)
        Pool().get('extra_data')._extra_data_structure_cache.clear()

    @classmethod
    def write(cls, *args):
        super(ExtraDataSubExtraDataRelation, cls).write(*args)
        Pool().get('extra_data')._extra_data_structure_cache.clear()


def with_extra_data_def(reverse_model_name, reverse_field_name, kind,
        getter=None):
    class WithExtraDataDefMixin(Model):
        '''
            Mixin to add extra data definitions (i.e. to define a list of
            extra_data to automatically set on linked objects)
        '''
        @classmethod
        def __setup__(cls):
            super(WithExtraDataDefMixin, cls).__setup__()
            cls.__rpc__.update({
                    'extra_data_structure': RPC(readonly=True),
                    })

        @classmethod
        def create(cls, vlist):
            created = super(WithExtraDataDefMixin, cls).create(vlist)
            Pool().get('extra_data')._extra_data_structure_cache.clear()
            return created

        @classmethod
        def delete(cls, ids):
            super(WithExtraDataDefMixin, cls).delete(ids)
            Pool().get('extra_data')._extra_data_structure_cache.clear()

        @classmethod
        def write(cls, *args):
            super(WithExtraDataDefMixin, cls).write(*args)
            Pool().get('extra_data')._extra_data_structure_cache.clear()

        @classmethod
        def validate(cls, instances):
            super(WithExtraDataDefMixin, cls).validate(instances)
            for elem in instances:
                elem._check_extra_data_def_consistency()

        def _check_extra_data_def_consistency(self):
            Pool().get('extra_data')._check_extra_data_def_consistency(
                self.extra_data_def)

        @classmethod
        def extra_data_structure(cls, ids):
            instances = cls.browse(ids)
            return {x.id: x._extra_data_structure() for x in instances}

        def _extra_data_structure(self):
            cache = Pool().get('extra_data')._extra_data_structure_cache
            cached = cache.get(str(self), -1)
            if cached != -1:
                return cached

            bases = {x.name: x._get_structure() for x in self.extra_data_def
                if not any([y for y in self.extra_data_def if y in x.parents])}

            cache.set(str(self), bases)
            return bases

        def refresh_extra_data(self, base_data):
            return Pool().get('extra_data')._refresh_extra_data(base_data,
                self._extra_data_structure())

    extra_data_def = fields.Many2Many(
        reverse_model_name, reverse_field_name, 'extra_data_def',
        'Extra Data', domain=[('kind', '=', kind)])
    if getter is not None:
        extra_data_def.relation_name = 'extra_data'
        extra_data_def.origin = None
        extra_data_def.target = None
        extra_data_def = fields.Function(extra_data_def, getter=getter)

    setattr(WithExtraDataDefMixin, 'extra_data_def', extra_data_def)

    return WithExtraDataDefMixin


def with_extra_data(kinds, schema=None, field_name='extra_data',
        field_string='Extra Data', getter_name=None, setter_name=None,
        create_string=True, create_summary=True):

    class WithExtraDataMixin(Model):
        pass

    field = fields.Dict('extra_data', field_string,
        domain=[('kind', 'in', kinds)],
        states={'invisible': ~Eval(field_name)} if schema else None)

    if not getter_name:
        @classmethod
        def post_setup(cls):
            super(WithExtraDataMixin, cls).__post_setup__()
            Pool().get('extra_data')._register_extra_data_provider(cls,
                'find_%s_value' % field_name, kinds)

        def finder(self, key, **kwargs):
            return getattr(self, field_name)[key]

        setattr(WithExtraDataMixin, '__post_setup__', post_setup)
        setattr(WithExtraDataMixin, 'find_%s_value' % field_name, finder)
    else:
        field = fields.Function(field, getter=getter_name, setter=setter_name)

    setattr(WithExtraDataMixin, field_name, field)

    if create_string:
        if create_string is True:
            string_name = '%s_string' % field_name
        else:
            string_name = create_string
        setattr(WithExtraDataMixin, string_name, field.translated(field_name))

    if create_summary:
        if create_summary is True:
            summary_name = '%s_summary' % field_name
        else:
            summary_name = create_summary
        summary = fields.Function(
            fields.Char('%s Summary' % field_string),
            'on_change_with_%s' % summary_name)
        setattr(WithExtraDataMixin, summary_name, summary)

        @fields.depends(field_name)
        def summary_getter(self, name=None):
            return Pool().get('extra_data').get_extra_data_summary([self],
                field_name)[self.id]

        setattr(WithExtraDataMixin, 'on_change_with_%s' % summary_name,
            summary_getter)

    if schema:
        def update_extra_data(self):
            if getattr(self, schema, None) is None:
                setattr(self, field_name, {})
                return
            setattr(self, field_name, getattr(self, schema).refresh_extra_data(
                    (getattr(self, field_name) or {}).copy()))

        setattr(WithExtraDataMixin, '_refresh_%s' % field_name,
            update_extra_data)

        @fields.depends(schema, field_name)
        def on_change_field(self):
            getattr(self, '_refresh_%s' % field_name)()

        setattr(WithExtraDataMixin, 'on_change_%s' % field_name,
            on_change_field)

        @fields.depends(schema, field_name)
        def on_change_schema(self):
            getattr(self, 'on_change_%s' % field_name)()

        setattr(WithExtraDataMixin, 'on_change_%s' % schema, on_change_schema)
    else:
        @staticmethod
        def default_values():
            ExtraData = Pool().get('extra_data')
            res = {}
            for kind in kinds:
                res.update(ExtraData._refresh_extra_data({},
                        ExtraData._global_extra_data_structure(kind)))
            return res

        setattr(WithExtraDataMixin, 'default_%s' % field_name, default_values)

    return WithExtraDataMixin

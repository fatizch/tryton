# encoding: utf-8
import copy
import datetime
from itertools import groupby

from sql import Literal, Column
from sql.functions import CurrentTimestamp
from sql.conditionals import Coalesce
from sql.aggregate import Max

from trytond import backend
from trytond.error import UserError
from trytond.rpc import RPC
from trytond.pool import PoolMeta
from trytond.model import Workflow, Model, fields as tryton_fields, \
    ModelSingleton, Unique
from trytond.pyson import Eval, PYSONEncoder, PYSON, Bool, Len, Or, If
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields, coop_string, utils, \
    coop_date
from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.report_engine import Printable

_STATES_WITH_SUBSTATES = ['declined']
STATUS_INCOMPATIBLE_WITH_ENDORSEMENTS = ['quote', 'declined', 'void']

__all__ = [
    'field_mixin',
    'values_mixin',
    'relation_mixin',
    'Contract',
    'ContractOption',
    'ContractOptionVersion',
    'ContractExtraData',
    'ContractActivationHistory',
    'Endorsement',
    'EndorsementContract',
    'EndorsementOption',
    'EndorsementOptionVersion',
    'EndorsementActivationHistory',
    'EndorsementExtraData',
    'EndorsementContact',
    'Configuration',
    'ReportTemplate',
    ]


def field_mixin(model):

    class Mixin(Model):
        name = fields.Function(fields.Char('Name'), 'get_name',
            searcher='search_name')
        endorsement_part = fields.Many2One('endorsement.part',
            'Endorsement Part', states={'invisible': True},
            ondelete='CASCADE', required=True, select=True)
        field = fields.Many2One('ir.model.field', 'Field', domain=[
                ('model.model', '=', model),
                ('ttype', 'in', ['boolean', 'integer', 'char', 'float',
                        'numeric', 'date', 'datetime', 'selection',
                        'many2one']),
                ], ondelete='CASCADE')
        definitions = fields.Function(
            fields.Many2Many('endorsement.definition', '', '', 'Definitions'),
            'get_definitions', searcher='search_definitions')

        @classmethod
        def __setup__(cls):
            super(Mixin, cls).__setup__()
            cls.__rpc__.update({
                    'get_keys': RPC(instantiate=0),
                    })

        @classmethod
        def _export_light(cls):
            return set(['field'])

        def get_rec_name(self, name):
            return self.field.rec_name

        @classmethod
        def search_rec_name(cls, name, clause):
            return [('field.rec_name',) + tuple(clause[1:])]

        def get_name(self, name):
            return self.field.name

        @classmethod
        def search_name(cls, name, clause):
            return [('field.name',) + tuple(clause[1:])]

        @classmethod
        def get_keys(cls, fields):
            pool = Pool()
            FieldModel = pool.get(model)
            keys = []
            for field in fields:
                key = {
                    'id': field.id,
                    'name': field.rec_name,
                    'string': field.field.field_description,
                    'type_': field.field.ttype,
                    }
                if field.field.ttype == 'selection':
                    real_field = FieldModel._fields[field.rec_name]
                    if isinstance(real_field.selection, list):
                        key['selection'] = list(real_field.selection)
                    else:
                        field_method = getattr(FieldModel,
                            real_field.selection)
                        if field_method.__self__ is None:
                            # Classmethod, we can call it
                            key['selection'] = field_method()
                        else:
                            # Instance method, fallback to string
                            key['type_'] = 'string'
                elif field.field.ttype in ('float', 'numeric'):
                    key['digits'] = FieldModel._fields[field.rec_name].digits
                    # In case of PYSON, we assume the worst
                    if isinstance(key['digits'][0], PYSON) or isinstance(
                            key['digits'][1], PYSON):
                        key['digits'] = (16, 4)
                elif field.field.ttype == 'many2one':
                    key['type_'] = 'integer'
                keys.append(key)
            return keys

        def get_definitions(self, name):
            Definition = Pool().get('endorsement.definition')
            return [x.id for x in Definition.search([
                        ('endorsement_parts', '=', self.endorsement_part.id)])]

        @classmethod
        def search_definitions(cls, name, clause):
            return [('endorsement_part.definitions',) + tuple(clause[1:])]

        @classmethod
        def _get_model(cls):
            return model

    return Mixin


class EndorsementRoot(object):
    @classmethod
    def __setup__(cls):
        super(EndorsementRoot, cls).__setup__()
        # cls._endorsed_dicts associates endorsement dict fields with the
        # endorsed model dict fields.
        # {'endorsed_extra_data': 'extra_data'} means that the
        # endorsed_extra_data field on the endorsement should be used to store
        # the extra_data field modifications on the target model
        cls._endorsed_dicts = {}

    @classmethod
    def __post_setup__(cls):
        super(EndorsementRoot, cls).__post_setup__()

        pool = Pool()
        endorsement_tree = {}
        for fname, field in cls._fields.iteritems():
            if not isinstance(field, fields.One2Many):
                continue
            Target = pool.get(field.model_name)
            if not issubclass(Target, EndorsementRoot):
                continue
            EndorsedField = pool.get(Target.values.schema_model)
            endorsement_tree[EndorsedField._get_model()] = (fname, field)
        cls._endorsement_tree = endorsement_tree
        cls._reversed_endorsed_dict = {
            v: k for k, v in cls._endorsed_dicts.iteritems()}

    def _get_field_for_model(self, target_model):
        return self.__class__._endorsement_tree[target_model]

    def is_null(self):
        '''
            Returns False if all endorsement related values (the 'values' dict
            field and recursively all endorsement related one2manys) are
            considered null, else True
        '''
        if getattr(self, 'values', None):
            return False
        for fname in self.__class__._endorsed_dicts:
            if getattr(self, fname, None):
                return False
        for fname, _ in self._endorsement_tree.itervalues():
            for elem in getattr(self, fname, []):
                if not elem.is_null():
                    return False
        return True

    def clean_up(self):
        '''
            Remove all 'dead' (as in 'is_null()') children endorsements, and
            returns own is_null status after trimming.
        '''
        for fname, _ in self._endorsement_tree.itervalues():
            values, new_values = getattr(self, fname, ()), []
            for elem in values:
                if not elem.clean_up():
                    new_values.append(elem)
            setattr(self, fname, new_values)
        return self.is_null()

    def set_applied_on(self, at_datetime):
        self.applied_on = at_datetime
        for fname, _ in self._endorsement_tree.itervalues():
            values, new_values = getattr(self, fname, ()), []
            for elem in values:
                elem.set_applied_on(at_datetime)
                new_values.append(elem)
            setattr(self, fname, new_values)


def values_mixin(value_model):

    class Mixin(EndorsementRoot, model.CoopSQL, model.CoopView):
        values = fields.Dict(value_model, 'Values')
        # applied_on need to be stored to be used as datetime_field
        applied_on = fields.Timestamp('Applied On', readonly=True)

        @classmethod
        def default_values(cls):
            return {}

        @classmethod
        def _view_look_dom_arch(cls, tree, type, field_children=None):
            pool = Pool()
            ValueModel = pool.get(value_model)
            values = tree.xpath('//field[@name="values"]')
            if values:
                values = values[0]
                vfields = ValueModel.search([
                        ('field.ttype', '=', 'many2one'),
                        ])
                used_ids = []
                for vfield in vfields:
                    if vfield.field.id in used_ids:
                        continue
                    field = copy.copy(values)
                    field.set('name', vfield.rec_name)
                    field.set('colspan', str(int(values.get('colspan')) / 2))
                    values.addnext(field)
                    label = copy.copy(values)
                    label.tag = 'label'
                    label.set('name', vfield.rec_name)
                    label.set('colspan', str(int(values.get('colspan')) / 2))
                    values.addnext(label)
                    used_ids.append(vfield.field.id)
            return super(Mixin, cls)._view_look_dom_arch(tree, type,
                field_children=field_children)

        @classmethod
        def fields_get(cls, fields_names=None):
            pool = Pool()
            ValueModel = pool.get(value_model)
            encoder = PYSONEncoder()

            fields = super(Mixin, cls).fields_get(fields_names=fields_names)
            if fields_names is None:
                fields_names = []

            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])
            used_ids = []
            for vfield in vfields:
                if vfield.field.id in used_ids:
                    continue
                if vfield.rec_name in fields_names or not fields_names:
                    fields[vfield.rec_name] = {
                        'type': 'many2one',
                        'name': vfield.rec_name,
                        'string': vfield.field.field_description,
                        'relation': vfield.field.relation,
                        'states': encoder.encode({
                                'invisible': ~Eval('values', {}).contains(
                                    str(vfield.rec_name)),
                                'readonly': cls.values.states.get('readonly',
                                    False),
                                }),
                        'datetime_field': 'applied_on',
                        'depends': (['values', 'applied_on'] +
                            cls.values.depends),
                        }
                    used_ids.append(vfield.field.id)
            return fields

        @classmethod
        def read(cls, ids, fields_names=None):
            pool = Pool()
            ValueModel = pool.get(value_model)
            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])
            vfields = dict((f.rec_name, f) for f in vfields)
            to_read = set()
            to_compute = set()
            to_compute_related = {}

            for field_name in fields_names or []:
                if '.' in field_name:
                    local_field_name, related_field_name = (
                        field_name.split('.', 1))
                    if local_field_name in vfields:
                        to_compute.add(local_field_name)
                        to_compute_related.setdefault(local_field_name,
                            []).append(related_field_name)
                        continue
                if field_name in vfields:
                    to_compute.add(field_name)
                else:
                    to_read.add(field_name)
            if to_compute:
                to_read.add('values')

            result = super(Mixin, cls).read(ids, fields_names=list(to_read))

            for row in result:
                for field_name in to_compute:
                    if row['values']:
                        row[field_name] = row['values'].get(field_name)
                    else:
                        row[field_name] = None

            related2values = {}
            for field_name in to_compute_related:
                Target = pool.get(vfields[field_name].field.relation)
                related2values.setdefault(field_name, {})
                for target in Target.read(
                        [r[field_name] for r in result if r[field_name]],
                        to_compute_related[field_name]):
                    target_id = target.pop('id')
                    values = related2values[field_name].setdefault(
                        target_id, {})
                    for row in result:
                        values[row['id']] = target
            if to_compute_related:
                for row in result:
                    for field_name in to_compute_related:
                        for related in to_compute_related[field_name]:
                            related_name = '.'.join((field_name, related))
                            value = None
                            if row[field_name]:
                                value = related2values[field_name][
                                    row[field_name]][row['id']][related]
                            row[related_name] = value
            return result

        @classmethod
        def default_get(cls, fields, with_rec_name=True):
            pool = Pool()
            ValueModel = pool.get(value_model)
            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])
            vfields = list(set([f.rec_name for f in vfields]))
            fields = [f for f in fields if f not in vfields]
            return super(Mixin, cls).default_get(fields,
                with_rec_name=with_rec_name)

        @staticmethod
        def convert_values(values):
            pool = Pool()
            ValueModel = pool.get(value_model)
            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])

            values = values.copy()

            new_values = {}
            for field in vfields:
                name = field.rec_name
                if name in values and name not in new_values:
                    new_values[name] = values.pop(name)
            if new_values:
                values.setdefault('values', {}).update(new_values)
            return values

        def clean(self):
            pool = Pool()
            self.values = {}
            for fname, field in self.__class__._fields.iteritems():
                if not isinstance(field, fields.One2Many):
                    continue
                Target = pool.get(field.model_name)
                if not isinstance(Target, EndorsementRoot):
                    continue
                setattr(self, fname, [])

        @classmethod
        def create(cls, vlist):
            vlist = [cls.convert_values(v) for v in vlist]
            return super(Mixin, cls).create(vlist)

        @classmethod
        def write(cls, *args):
            actions = iter(args)
            new_actions = []
            for records, values in zip(actions, actions):
                if not records:
                    continue
                if 'values' in values:
                    new_actions += [records, cls.convert_values(values)]
                else:
                    for record in records:
                        values = values.copy()
                        values['values'] = record.values
                        new_actions += [[record], cls.convert_values(values)]
            if new_actions:
                return super(Mixin, cls).write(*new_actions)

        def get_endorsed_record(self):
            raise NotImplementedError

        def get_summary(self, model, base_object=None):
            pool = Pool()
            Date = pool.get('ir.date')
            lang = pool.get('res.user')(Transaction().user).language
            ValueModel = pool.get(model)
            vals = []
            if getattr(self, 'action', None):
                if self.action == 'update':
                    base_object = self.base_instance
            if not self.values:
                return ''
            for k, v in self.values.iteritems():
                if base_object and hasattr(base_object, k):
                    prev_value = getattr(base_object, k, '') or ''
                else:
                    prev_value = ''
                field = ValueModel._fields[k]
                if isinstance(field, tryton_fields.Many2One):
                    if v:
                        vals.append((k, field,
                                prev_value.rec_name if prev_value else '',
                                self.get_name_for_summary(field, v)))
                    else:
                        vals.append((k, field,
                                prev_value.rec_name if prev_value else '', ''))
                elif isinstance(field, tryton_fields.Date) or \
                    (isinstance(field, tryton_fields.Function) and (isinstance(
                                field._field, tryton_fields.Date))):
                    if prev_value:
                        prev_value = Date.date_as_string(prev_value, lang)
                    if v:
                        v = Date.date_as_string(v, lang)
                    vals.append((k, field, prev_value, v))
                else:
                    vals.append((k, field, prev_value, v if v is not None
                            else ''))
            for fname, target_fname in \
                    self.__class__._endorsed_dicts.iteritems():
                if base_object:
                    prev_value = ', '.join(coop_string.translate_value(
                            base_object, target_fname).split('\n'))
                else:
                    prev_value = ''
                new_value = ', '.join(coop_string.translate_value(self,
                        fname).split('\n'))
                if prev_value != new_value:
                    vals.append((target_fname, getattr(ValueModel,
                                target_fname), prev_value, new_value))
            if hasattr(self, 'action') and self.action == 'add':
                return [u'%s : → %s' % (coop_string.translate(
                        ValueModel, fname, ffield.string, 'field'), new)
                for fname, ffield, _, new in vals]
            return [u'%s : %s → %s' % (coop_string.translate(
                        ValueModel, fname, ffield.string, 'field'), old, new)
                for fname, ffield, old, new in vals if old != new]

        def get_records_before_application(self, current_records,
                parent_endorsed_record=None):
            if not parent_endorsed_record:
                parent_endorsed_record = self.get_endorsed_record()
            for endorsement_fname in [x[0] for x
                    in self._endorsement_tree.values()]:
                sub_endorsements = getattr(self, endorsement_fname, [])
                if not sub_endorsements:
                    continue
                current_records.extend(getattr(parent_endorsed_record,
                        endorsement_fname))
                for sub_endorsement in sub_endorsements:
                    sub_endorsement.get_records_before_application(
                        current_records, parent_endorsed_record)

        def update_after_application(self, parent_endorsed_record=None,
                pre_application_records=None, current_records=None):
            if not parent_endorsed_record:
                parent_endorsed_record = self.get_endorsed_record()
            for endorsement_fname in [x[0] for x
                    in self._endorsement_tree.values()]:
                sub_endorsements = getattr(self, endorsement_fname, [])
                if sub_endorsements:
                    current_records = list(getattr(parent_endorsed_record,
                            endorsement_fname))
                    for sub_endorsement in sub_endorsements:
                        sub_endorsement.update_after_application(
                            parent_endorsed_record, pre_application_records,
                            current_records)

        def update_after_cancellation(self, parent_endorsed_record=None):
            if not parent_endorsed_record:
                parent_endorsed_record = self.get_endorsed_record()
            for endorsement_fname in [x[0] for x
                    in self._endorsement_tree.values()]:
                sub_endorsements = getattr(self, endorsement_fname, [])
                for sub_endorsement in sub_endorsements:
                    sub_endorsement.update_after_cancellation(
                        parent_endorsed_record)

        def endorsement_matches_record(self, record):
            # If this method crashes with IndexError,it is probably because
            # there is a Many2One set to None in the endorsement values
            # and the corresponding field in the added record
            # was set at endorsement application according to the
            # reverse One2Many on the parent object.

            if record.__name__ != self._model_name:
                return False
            ignore_fields = self._ignore_fields_for_matching()
            for k, v in self.values.iteritems():
                if k in ignore_fields:
                    continue
                if not hasattr(record, k):
                    return False
                field = record._fields[k]
                if isinstance(field, tryton_fields.Property):
                    field = field._field
                if isinstance(field, (tryton_fields.Many2One,
                        tryton_fields.Reference, tryton_fields.One2One)):
                    if v is None and getattr(record, k) is not None:
                        return False
                    elif getattr(record, k) and not getattr(record, k).id == v:
                        return False
                else:
                    if not getattr(record, k) == v:
                        return False
            return True

        @classmethod
        def _ignore_fields_for_matching(cls):
            return set()

        def apply_values(self):
            values = (self.values if self.values else {}).copy()
            for fname, target_fname in \
                    self.__class__._endorsed_dicts.iteritems():
                values[target_fname] = getattr(self, fname, {}).copy()
            return values

        def get_name_for_summary(self, field_, instance_id):
            pool = Pool()
            return pool.get(field_.model_name)(instance_id).rec_name

    return Mixin


def relation_mixin(value_model, field, model, name):

    class Mixin(values_mixin(value_model)):
        _func_key = 'func_key'
        _relation_field_name = field
        _model_name = model

        action = fields.Selection([
                ('add', 'Add'),
                ('update', 'Update'),
                ('remove', 'Remove'),
                ], 'Action')
        relation = fields.Integer('Relation',
            states={
                'required': Eval('action').in_(['update', 'remove']),
                'invisible': Eval('action') == 'add',
                },
            depends=['action'])
        func_key = fields.Function(
            fields.Char('Functional Key'), 'get_func_key')

        @classmethod
        def __setup__(cls):
            super(Mixin, cls).__setup__()
            cls.values.states = {
                'invisible': Eval('action') == 'remove',
                }
            cls.values.depends = ['action']
            cls._error_messages.update({
                    'mes_remove_version': 'Remove version of',
                    'mes_new_version': 'New version',
                    'mes_update_version': 'Update %s',
                    })

        def is_null(self):
            return super(Mixin, self).is_null() and self.action != 'remove'

        @classmethod
        def read(cls, ids, fields_names=None):
            BaseModel = Pool().get(model)
            relation_fields_to_read = [fname for fname in fields_names
                if fname in cls._fields and isinstance(cls._fields[fname],
                    tryton_fields.Function) and fname in BaseModel._fields
                and not cls._fields[fname].getter]
            if relation_fields_to_read:
                result = super(Mixin, cls).read(ids, list(set(fields_names) -
                        set(relation_fields_to_read)) + ['relation', 'values'])
            else:
                return super(Mixin, cls).read(ids, fields_names)

            relation_values = BaseModel.read([x['relation'] for x in result
                    if x['relation']], relation_fields_to_read)
            relation_values = {x['id']: x for x in relation_values}
            for row in result:
                for fname in relation_fields_to_read:
                    if 'values' in row and fname in row['values']:
                        row[fname] = row['values'][fname]
                    elif row['relation']:
                        row[fname] = relation_values[row['relation']][fname]
                    else:
                        row[fname] = None
            return result

        @staticmethod
        def default_action():
            return 'add'

        def get_relation(self, name):
            return self.relation

        @classmethod
        def set_relation(cls, records, name, value):
            cls.write(records, {
                    'relation': value,
                    })

        @classmethod
        def _import_json(cls, values, main_object=None):
            pool = Pool()
            the_model = pool.get(model)
            if 'values' in values:
                values_field = values['values']
                if values_field:
                    new_values_field = {}
                    for key, value in values_field.iteritems():
                        field = the_model._fields[key]
                        # TODO handle Reference fields
                        if isinstance(field, tryton_fields.Many2One) and value:
                            Target = field.get_target()
                            target = Target.import_json(value)
                            target.save()
                            new_values_field[key] = target.id
                        else:
                            new_values_field[key] = value
                    values['values'] = new_values_field
            return super(Mixin, cls)._import_json(values, main_object)

        def export_json(self, skip_fields=None, already_exported=None,
                output=None, main_object=None, configuration=None):
            pool = Pool()
            the_model = pool.get(model)
            values = super(Mixin, self).export_json(skip_fields,
                already_exported, output, main_object, configuration)
            if 'values' in values:
                values_field = values['values']
                if values_field:
                    new_values_field = {}
                    for key, value in values_field.iteritems():
                        field = the_model._fields[key]
                        if isinstance(field, tryton_fields.Many2One) and value:
                            Target = field.get_target()
                            target, = Target.search([('id', '=', value)])
                            export = []
                            target.export_json(output=export,
                                configuration=configuration)
                            new_values_field[key] = export[-1]
                        else:
                            new_values_field[key] = value
                    values['values'] = new_values_field
            return values

        def apply_values(self):
            values = super(Mixin, self).apply_values()
            if self.action == 'add':
                return ('create', [values])
            elif self.action == 'update':
                return ('write', [getattr(self, field).id], values)
            elif self.action == 'remove':
                return ('delete', [getattr(self, field).id])

        @property
        def base_instance(self):
            if not self.relation:
                return None
            with Transaction().set_context(
                    _datetime=self.applied_on,
                    _datetime_exclude=True):
                return Pool().get(model)(self.relation)

        def get_summary(self, model, base_object=None):
            if self.action == 'remove':
                return ['remove_section', '%s %s' % (self.raise_user_error(
                        'mes_remove_version', raise_exception=False),
                    self.base_instance.rec_name)]
            elif self.action == 'add':
                result = ['new_section', '%s:' % self.raise_user_error(
                    'mes_new_version', raise_exception=False)]
                result += [super(Mixin, self).get_summary(model, base_object)]
                return result
            elif self.action == 'update':
                result = ['update_section', '%s: ' % self.raise_user_error(
                    'mes_update_version', (base_object.rec_name),
                    raise_exception=False)]
                result += [super(Mixin, self).get_summary(model, base_object)]
                return result
            return super(Mixin, self).get_summary(model, base_object)

        def get_func_key(self, name):
            return getattr(self, field).func_key if getattr(self, field) and \
                hasattr(getattr(self, field), 'func_key') else ''

        def get_records_before_application(self, current_records,
                parent_endorsed_record=None):
            if self.action == 'update':
                parent_endorsed_record = getattr(self,
                    getattr(self, '_relation_field_name'))
                super(Mixin, self).get_records_before_application(
                    current_records, parent_endorsed_record)

        def update_after_application(self, parent_endorsed_record=None,
                pre_application_records=None, current_records=None):
            if self.action == 'add':
                self.set_relation_for_added_record(current_records,
                    pre_application_records)
            parent_endorsed_record = getattr(self,
                getattr(self, '_relation_field_name'))
            super(Mixin, self).update_after_application(parent_endorsed_record,
                pre_application_records, current_records)

        def update_after_cancellation(self, parent_endorsed_record=None):
            if self.action == 'add':
                self.remove_relation()
            else:
                parent_endorsed_record = getattr(self,
                    getattr(self, '_relation_field_name'))
            super(Mixin, self).update_after_cancellation(
                parent_endorsed_record)

        def remove_relation(self):
            self.set_relation([self], None, None)

        def set_relation_for_added_record(self, current_records,
                previous_records):
            relation_record = [x for x in current_records
                if x not in previous_records and
                self.endorsement_matches_record(x)][0]
            self.set_relation([self], None, relation_record.id)
            return relation_record

    setattr(Mixin, field, fields.Function(fields.Many2One(model, name,
                datetime_field='applied_on',
                states={
                    'required': Eval('action').in_(['update', 'remove']),
                    'invisible': Eval('action') == 'add',
                    },
                depends=['action']),
            'get_relation', setter='set_relation'))

    return Mixin


class Contract(CogProcessFramework):
    __metaclass__ = ClassAttr
    _history = True
    __name__ = 'contract'

    latest_endorsement = fields.Function(
        fields.Many2One('endorsement.contract', 'Last Endorsement'),
        'get_latest_endorsement')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'revert_current_endorsement': {},
                'start_endorsement': {
                    'invisible': Eval('status') == 'quote',
                    }
                })
        cls._buttons['button_stop']['invisible'] = True

    @classmethod
    def getter_activation_history(cls, contracts, names):
        today = utils.today()
        values = cls.activation_history_base_values(contracts)

        if Transaction().context.get('_datetime', None):
            # TODO: handle __history__ with sql
            for contract in contracts:
                if not contract.activation_history:
                    continue
                period = utils.get_value_at_date(contract.activation_history,
                    today, date_field='start_date')
                if not period:
                    period = contract.activation_history[0]
                values['start_date'][contract.id] = period.start_date
                values['end_date'][contract.id] = period.end_date
            return values
        return super(Contract, cls).getter_activation_history(contracts,
            names)

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/group[@id="endorsement_buttons"]',
                'states',
                {'invisible': True}
                )]

    def get_latest_endorsement(self, name):
        Endorsement = Pool().get('endorsement')
        endorsement = Endorsement.search([
                ('contracts', '=', self.id),
                ('state', 'not in', ['draft', 'canceled', 'declined']),
                ], order=[('application_date', 'DESC')], limit=1)
        if endorsement:
            return endorsement[0].id

    def related_attachments_resources(self):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        endorsements = Endorsement.search([('contracts', '=', self.id),
                ('state', '=', 'applied')])
        return super(Contract, self).related_attachments_resources() + [
            str(x) for x in endorsements]

    @classmethod
    @model.CoopView.button
    def revert_current_endorsement(cls, contracts):
        Endorsement = Pool().get('endorsement')
        endorsements_to_cancel = set()
        for contract in contracts:
            last_endorsement = Endorsement.search([
                    ('contracts', '=', contract.id),
                    ('state', '=', 'in_progress'),
                    ], order=[('application_date', 'DESC')], limit=1)
            if last_endorsement:
                endorsements_to_cancel.add(last_endorsement[0])
        if endorsements_to_cancel:
            endorsements_to_cancel = list(endorsements_to_cancel)
            Endorsement.draft(endorsements_to_cancel)
            Endorsement.delete(endorsements_to_cancel)
        return 'close'

    @classmethod
    @model.CoopView.button_action('endorsement.act_start_endorsement')
    def start_endorsement(cls, contracts):
        pass

    @classmethod
    def apply_in_progress_endorsement(cls, contracts):
        Endorsement = Pool().get('endorsement')
        endorsements = Endorsement.search([
                ('contracts', 'in', [x.id for x in contracts]),
                ('state', '=', 'in_progress')])
        if not endorsements:
            cls.raise_user_error('no_in_progress_endorsements')
        Endorsement.apply(endorsements)

    def update_start_date(self, caller=None):
        if not caller:
            return
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        if not isinstance(caller, ContractEndorsement):
            return
        if not caller.values.get('start_date', None):
            return
        self.start_date = caller.values['start_date']
        self.save()

    @classmethod
    def _calculate_methods_after_endorsement(cls):
        return {'calculate_activation_dates'}

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        # Create endorsements for rollback points BEFORE super
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        endorsement = ContractEndorsement.new_rollback_point(contracts,
            at_date, 'endorsement.stop_contract_definition', {'values': {
                    'status': 'terminated',
                    'sub_status': termination_reason.id,
                    'end_date': at_date,
                    }})
        endorsement.save()

        return super(Contract, cls).terminate(contracts, at_date,
            termination_reason)

    @classmethod
    def void(cls, contracts, void_reason):
        # Create endorsements for rollback points BEFORE super
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        endorsement = ContractEndorsement.new_rollback_point(contracts,
            contracts[0].start_date, 'endorsement.void_contract_definition',
            {'values': {
                    'status': 'void',
                    'sub_status': void_reason.id,
                    }})
        endorsement.save()

        super(Contract, cls).void(contracts, void_reason)

    @classmethod
    def reactivate(cls, contracts):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        previous_dates = {contract.id: contract.end_date
            for contract in contracts}
        super(Contract, cls).reactivate(contracts)
        new_dates = {contract.id: contract.end_date for contract in contracts}
        endorsements = []
        for dates, contract_group in groupby(contracts,
                lambda x: (previous_dates[x.id], new_dates[x.id])):
            endorsements.append(ContractEndorsement.new_rollback_point(
                    list(contract_group), coop_date.add_day(dates[0], 1),
                    'endorsement.reactivate_contract_definition',
                    {'values': {
                            'status': 'active',
                            'end_date': dates[1],
                            'sub_status': None,
                            }}))
        Endorsement.save(endorsements)


class ContractOption(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.option'


class ContractOptionVersion(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.option.version'

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Option = pool.get('contract.option')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        option_hist = Option.__table_history__()
        version_hist = cls.__table_history__()

        # Migration from 1.4 : Create default contract.option.version
        to_migrate = not TableHandler.table_exist(cursor, cls._table +
            '__history')
        super(ContractOptionVersion, cls).__register__(module)

        if to_migrate:
            version_h = TableHandler(cursor, cls, module, history=True)
            # Delete previously created history, to have full control
            cursor.execute(*version_hist.delete())
            cursor.execute(*version_hist.insert(
                    columns=[
                        version_hist.create_date, version_hist.create_uid,
                        version_hist.write_date, version_hist.write_uid,
                        version_hist.extra_data, version_hist.option,
                        version_hist.id, Column(version_hist, '__id')],
                    values=option_hist.select(
                        option_hist.create_date, option_hist.create_uid,
                        option_hist.write_date, option_hist.write_uid,
                        Literal('{}').as_('extra_data'),
                        option_hist.id.as_('option'),
                        option_hist.id.as_('id'),
                        Column(option_hist, '__id').as_('__id'))))
            cursor.execute(*version_hist.select(
                    Max(Column(version_hist, '__id'))))
            cursor.setnextid(version_h.table_name + '__',
                cursor.fetchone()[0] or 0 + 1)


class ContractActivationHistory(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.activation_history'

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.4 add active field
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        do_migrate = False
        history_table = TableHandler(cursor, cls, history=True)
        if not history_table.column_exist('active'):
            do_migrate = True
        super(ContractActivationHistory, cls).__register__(module_name)
        if not do_migrate:
            return
        cursor.execute("UPDATE contract_activation_history__history "
            "SET active = 'TRUE'")


class ContractExtraData(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.extra_data'


class Endorsement(Workflow, model.CoopSQL, model.CoopView, Printable):
    'Endorsement'

    __metaclass__ = PoolMeta
    __name__ = 'endorsement'
    _func_key = 'number'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True, required=True)
    applicant = fields.Many2One('party.party', 'Applicant',
        ondelete='RESTRICT')
    application_date = fields.DateTime('Application Date', readonly=True,
        states={'invisible': Eval('state', '') == 'draft'},
        depends=['state'])
    application_date_str = fields.Function(
        fields.Char('Application Date'),
        'on_change_with_application_date_str')
    rollback_date = fields.Timestamp('Rollback Date', readonly=True)
    applied_by = fields.Many2One('res.user', 'Applied by', readonly=True,
        states={'invisible': Eval('state', '') == 'draft'},
        depends=['state'], ondelete='RESTRICT')
    contract_endorsements = fields.One2Many('endorsement.contract',
        'endorsement', 'Contract Endorsement', delete_missing=True)
    definition = fields.Many2One('endorsement.definition', 'Definition',
        required=True, ondelete='RESTRICT')
    effective_date = fields.Date('Effective Date')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('applied', 'Applied'),
            ('canceled', 'Canceled'),
            ('declined', 'Declined'),
            ], 'State', readonly=True)
    state_string = state.translated('state')
    sub_state = fields.Many2One('endorsement.sub_state', 'Details on state',
        states={
            'required': Bool(Eval('sub_state_required')),
            'invisible': ~Eval('sub_state_required')
            },
        domain=[('state', '=', Eval('state'))],
        depends=['state', 'sub_state_required'], ondelete='RESTRICT')
    sub_state_required = fields.Function(
        fields.Boolean('Sub State Required'),
        'on_change_with_sub_state_required')
    contracts = fields.Function(
        fields.Many2Many('contract', '', '', 'Contracts'),
        'get_contracts', searcher='search_contracts')
    endorsement_summary = fields.Function(
        fields.Text('Endorsement Summary', readonly=True),
        'get_endorsement_summary')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        target_not_required=True)
    contracts_name = fields.Function(
        fields.Char('Contracts Name'),
        'get_contracts_name')
    subscribers_name = fields.Function(
        fields.Char('Subscribers Name'),
        'get_subscribers_name')
    generated_by = fields.Many2One('endorsement', 'Generated By',
        ondelete='SET NULL', select=True, readonly=True,
        states={'invisible': ~Eval('generated_by')})
    generated_endorsements = fields.One2Many('endorsement', 'generated_by',
        'Generated Endorsements', target_not_required=True)

    @classmethod
    def __setup__(cls):
        super(Endorsement, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'applied'),
                ('draft', 'in_progress'),
                ('draft', 'declined'),
                ('in_progress', 'draft'),
                ('in_progress', 'applied'),
                ('applied', 'canceled'),
                ('declined', 'draft'),
                ))
        cls._buttons.update(
            {
                'start_endorsement': {
                    'invisible': ~Eval('state').in_(['draft'])
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['in_progress']),
                    },
                'apply': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'cancel': {
                    'invisible': ~Eval('state').in_(['applied']),
                    },
                'decline': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'reset': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'open_contract': {
                    'invisible': Or(~Eval('state').in_(['applied']),
                        Len(Eval('contract_endorsements', [])) == Len([])),
                    },
                'button_decline_endorsement': {
                    'invisible': ~Eval('state').in_(['draft'])
                    },
                })
        cls._order = [('application_date', 'DESC'), ('create_date', 'DESC')]
        cls.__rpc__.update({'ws_create_endorsements': RPC(readonly=False)})
        cls._error_messages.update({
                'invalid_format': 'Invalid file format',
                'no_sequence_defined': 'No sequence defined in configuration',
                })
        t = cls.__table__()
        cls._sql_constraints = [
            ('number_uniq', Unique(t, t.number),
                'The endorsement number must be unique.')
        ]

    @classmethod
    def view_attributes(cls):
        return super(Endorsement, cls).view_attributes() + [
            ('/tree', 'colors', If(Eval('state') == 'applied', 'green',
                    If(Eval('state') == 'canceled', 'grey', 'black')))]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('endorsement.configuration')

        config = Configuration(1)
        if not config.endorsement_number_sequence:
            cls.raise_user_error('no_sequence_defined')
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if not values.get('number', None):
                values['number'] = Sequence.get_id(
                    config.endorsement_number_sequence.id)
        return super(Endorsement, cls).create(vlist)

    @classmethod
    def default_state(cls):
        return 'draft'

    def get_rec_name(self, name):
        return '%s' % self.definition.name

    def get_contracts_name(self, name):
        return '\n'.join([x.rec_name for x in self.contracts])

    def get_subscribers_name(self, name):
        return '\n'.join([x.subscriber.rec_name for x in self.contracts])

    def get_object_for_contact(self):
        return self.contracts[0]

    def get_contact(self):
        return self.contracts[0].get_contact()

    def get_sender(self):
        return self.contracts[0].company.party

    def get_report_functional_date(self, event_code):
        if event_code == 'apply_endorsement':
            return self.effective_date
        return super(Endorsement, self).get_report_functional_date(event_code)

    @fields.depends('application_date')
    def on_change_with_application_date_str(self, name=None):
        if self.application_date:
            return Pool().get('ir.date').datetime_as_string(
                self.application_date)

    @fields.depends('state')
    def on_change_with_sub_state_required(self, name=None):
        return self.state in _STATES_WITH_SUBSTATES

    def get_contracts(self, name):
        return [x.contract.id for x in self.contract_endorsements]

    @classmethod
    def format_summary(cls, summary, indent=0, style=None):
        inc = 2
        res = ''
        if type(summary) in (str, unicode):
            if not summary:
                # Empty line, no styling
                return '\n'
            if summary.endswith('section'):
                return '\n'
            elif u'→' in summary:
                elems = summary.split(u'→')
                return ' ' * indent + elems[0] + u'→' + "<b>" + elems[1] +\
                    "</b>" + '\n'
            elif not style:
                style = 'italic'

            if style == 'italic':
                pre, post = '<i>', '</i>'
            elif style == 'bold':
                pre, post = '<b>', '</b>'
            elif style == 'underline':
                pre, post = '<u>', '</u>'
            elif style == 'center':
                pre, post = "<p align='center'> <span size='12'> <b>", \
                    "</b> </span> </p>"
            else:
                pre = post = ''
            res += ' ' * indent + pre + summary + post + '\n'
        else:
            for i, item in enumerate(summary):
                if i == 1 and summary[0] == 'definition_section':
                    res += cls.format_summary(item, indent, style='underline')
                elif i == 1 and summary[0] == 'title_section':
                    res += cls.format_summary(item, indent, style='center')
                else:
                    res += cls.format_summary(item, indent=indent + inc)
        return res

    def raw_endorsement_summary(self):
        return [x.get_endorsement_summary(None)
            for x in self.all_endorsements()]

    def get_endorsement_summary(self, name):
        """The get_endorsement_summary method of all objects returned by
        self.all_endorsements returns a list structured like so:

        [
            'definition_section',
            u'some_endorsement_definition_name',
            [
                'some_element_change_section',
                u'Some Elements Modifications: ',
                [
                    [
                        'new_section',
                        u'New Version: ',
                        [
                            u'bar:  → spam',
                            u'foo: → spam'
                        ]]]]]

        Optionnaly, such structure can be included in a higer level
        title section like so : ['title_section, 'Some Title', the_structure]
        The list of such structures is then parsed recursively by
        format_summary to produce an indented and formatted text,
        according to the names of the sections.
        """
        result = [x.get_endorsement_summary(name)
                for x in self.all_endorsements()]
        return self.format_summary(result)

    @classmethod
    def search_contracts(cls, name, clause):
        return [('contract_endorsements.contract',) + tuple(clause[1:])]

    @staticmethod
    def order_application_date_str(tables):
        table, _ = tables[None]
        return [Coalesce(table.application_date, datetime.date.min)]

    def all_endorsements(self):
        return self.contract_endorsements

    def find_parts(self, endorsement_part):
        # Finds the effective endorsement depending on the provided
        # endorsement part
        if endorsement_part.kind in ('contract', 'option', 'extra_data'):
            return self.contract_endorsements

    def new_endorsement(self, endorsement_part):
        # Return a new endorsement instantiation depending on the endorsement
        # part
        if endorsement_part.kind in ('contract', 'option',
                'activation_history', 'extra_data'):
            return Pool().get('endorsement.contract')(endorsement=self)

    @classmethod
    def group_per_model(cls, endorsements):
        return {
            'endorsement.contract': [contract_endorsement
                for endorsement in endorsements
                for contract_endorsement in endorsement.contract_endorsements]
            }

    @classmethod
    def apply_order(cls):
        return ['endorsement.contract']

    @classmethod
    def _draft(cls, endorsements):
        pool = Pool()
        endorsements_per_model = cls.group_per_model(endorsements)
        for model_name in cls.apply_order():
            if model_name not in endorsements_per_model:
                continue
            ModelClass = pool.get(model_name)
            ModelClass.draft(endorsements_per_model[model_name])
            for value_endorsement in endorsements_per_model[model_name]:
                value_endorsement.update_after_cancellation()
        cls.run_methods(endorsements, 'draft')

    @classmethod
    @model.CoopView.button
    @Workflow.transition('canceled')
    def cancel(cls, endorsements):
        pool = Pool()
        Event = pool.get('event')
        cls._draft(endorsements)
        cls.write(endorsements, {
                'rollback_date': None,
                'state': 'canceled',
                })
        Event.notify_events(endorsements, 'cancel_endorsement')

    @classmethod
    @model.CoopView.button
    @Workflow.transition('declined')
    def decline(cls, endorsements, reason=None):
        pool = Pool()
        Event = pool.get('event')
        cls.write(endorsements, {
                'state': 'declined',
                'sub_state': reason,
                })
        Event.notify_events(endorsements, 'decline_endorsement',
                description=(reason.name if reason else None))

    @classmethod
    @model.CoopView.button
    @Workflow.transition('draft')
    def draft(cls, endorsements):
        cls._draft([x for x in endorsements if x.state != 'declined'])
        cls.write(endorsements, {
                'applied_by': None,
                'application_date': None,
                'rollback_date': None,
                'state': 'draft',
                'sub_state': None,
                })

    @classmethod
    @Workflow.transition('in_progress')
    def in_progress(cls, endorsements):
        pool = Pool()
        groups = cls.group_per_model(endorsements)
        for model_name, values in groups.iteritems():
            pool.get(model_name).check_in_progress_unicity(values)
        cls.write(endorsements, {'rollback_date': CurrentTimestamp()})

    @classmethod
    @model.CoopView.button
    @Workflow.transition('applied')
    def apply(cls, endorsements):
        pool = Pool()
        Event = pool.get('event')
        endorsements_per_model = cls.group_per_model(endorsements)
        for model_name in cls.apply_order():
            if model_name not in endorsements_per_model:
                continue
            ModelClass = pool.get(model_name)

            # We record the states of records before application
            # To be able to set the relation field on an endorsement
            # That will create a new record.
            records_per_endorsement = {}
            for value_endorsement in endorsements_per_model[model_name]:
                current_records = []
                value_endorsement.get_records_before_application(
                    current_records)
                records_per_endorsement[
                    value_endorsement] = current_records
            ModelClass.apply(endorsements_per_model[model_name])
            for value_endorsement in endorsements_per_model[model_name]:
                value_endorsement.update_after_application(
                    pre_application_records=records_per_endorsement[
                        value_endorsement])

        set_rollback, do_not_set_rollback = [], []
        for endorsement in endorsements:
            if endorsement.rollback_date:
                do_not_set_rollback.append(endorsement)
            else:
                set_rollback.append(endorsement)
        if set_rollback:
            cls.write(set_rollback, {
                    'applied_by': Transaction().user,
                    'rollback_date': CurrentTimestamp(),
                    'application_date': datetime.datetime.now(),
                    })
        if do_not_set_rollback:
            cls.write(do_not_set_rollback, {
                    'applied_by': Transaction().user,
                    'application_date': datetime.datetime.now(),
                    })
        cls.write(endorsements, {'state': 'applied'})

        cls.run_methods(endorsements, 'apply')

        if not Transaction().context.get('will_be_rollbacked', False):
            Event.notify_events(endorsements, 'apply_endorsement')

    @classmethod
    @model.CoopView.button
    def reset(cls, endorsements):
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        for endorsement in endorsements:
            tmp_contracts = endorsement.contracts
            ContractEndorsement.delete(endorsement.contract_endorsements)
            endorsement.contract_endorsements = None
            endorsement.contract_endorsements = ContractEndorsement.create(
                [{'contract': x, 'endorsement': endorsement}
                    for x in tmp_contracts])
            endorsement.effective_date = None
            endorsement.save()

    @classmethod
    def run_methods(cls, endorsements, kind):
        Method = Pool().get('ir.model.method')
        if kind == 'apply':
            method_name = 'get_methods_for_model'
        elif kind == 'draft':
            method_name = 'get_draft_methods_for_model'
        else:
            raise NotImplementedError
        # Force reload endorsement list
        for idx, endorsement in enumerate(cls.browse(
                    [x.id for x in endorsements])):
            endorsements[idx] = endorsement
        endorsements_per_model = cls.group_per_model(endorsements)
        for model_name in cls.apply_order():
            for endorsement in endorsements_per_model.get(model_name, []):
                if kind == 'draft' and endorsement.state == 'in_progress':
                    # Was never applied, so application methods were not
                    # called, so no need to cancel them
                    continue
                instance = endorsement.get_endorsed_record()
                method_names = getattr(endorsement.definition, method_name)(
                    instance.__name__)
                methods = [Method.get_method(instance.__name__, x)
                    for x in method_names]
                if not methods:
                    continue
                methods.sort(key=lambda x: x.priority)
                for method in methods:
                    method.execute(endorsement, instance)
                instance.save()

    @classmethod
    @model.CoopView.button_action('endorsement.act_decline_endorsement')
    def button_decline_endorsement(cls, endorsements):
        pass

    @classmethod
    def soft_apply(cls, endorsements):
        with Transaction().set_context(endorsement_soft_apply=True,
                will_be_rollbacked=True):
            cls.apply(endorsements)

    @classmethod
    def apply_for_preview(cls, endorsements):
        cls.apply(endorsements)

    @classmethod
    @model.CoopView.button_action('endorsement.act_contract_open')
    def open_contract(cls, endorsements):
        pass

    def extract_preview_values(self, extraction_method, **kwargs):
        pool = Pool()
        current_values, old_values, new_values = {}, {}, {}
        for unitary_endorsement in self.all_endorsements():
            endorsed_record = unitary_endorsement.get_endorsed_record()
            endorsed_model, endorsed_id = (endorsed_record.__name__,
                endorsed_record.id)
            current_values['%s,%i' % (endorsed_model, endorsed_id)] = \
                extraction_method(endorsed_record, **kwargs)
        if self.application_date:
            for unitary_endorsement in self.all_endorsements():
                endorsed_record = unitary_endorsement.get_endorsed_record()
                endorsed_model, endorsed_id = (endorsed_record.__name__,
                    endorsed_record.id)
                old_record = utils.get_history_instance(endorsed_model,
                    endorsed_id, self.application_date)
                old_values['%s,%i' % (endorsed_model, endorsed_id)] = \
                    extraction_method(old_record, **kwargs)
            new_values = current_values
        else:
            # Make sure all changes are saved
            assert not self._save_values

            # Apply endorsement in a sandboxed transaction
            with Transaction().new_cursor():
                with Transaction().set_context(will_be_rollbacked=True):
                    applied_self = self.__class__(self.id)
                    self.apply_for_preview([applied_self])
                    for unitary_endorsement in applied_self.all_endorsements():
                        endorsed_record = \
                            unitary_endorsement.get_endorsed_record()
                        endorsed_model, endorsed_id = (
                            endorsed_record.__name__, endorsed_record.id)
                        record = pool.get(endorsed_model)(endorsed_id)
                        new_values['%s,%i' % (endorsed_model, endorsed_id)] = \
                            extraction_method(record, **kwargs)
                    old_values = current_values
                    Transaction().cursor.rollback()
            return {'old': old_values, 'new': new_values}

    @classmethod
    def _export_light(cls):
        return (super(Endorsement, cls)._export_light() |
            set(['applied_by', 'applicant', 'definition']))

    @classmethod
    def ws_create_endorsements(cls, endorsements_dict):
        'This method is a standard API for webservice use'
        result = {}
        for ext_id, objects in endorsements_dict.iteritems():
            message = []
            result[ext_id] = {'return': True, 'messages': message}
            try:
                for item in objects:
                    if item['__name__'] == 'endorsement':
                        endorsement = cls.import_json(item)
                        message.append({
                            'number': endorsement.number
                            })
                    else:
                        cls.raise_user_error('invalid_format')
            except UserError as exc:
                Transaction().cursor.rollback()
                message.append({'error': exc.message})
                return {ext_id: {
                        'return': False,
                        'messages': message,
                    }}
        return result

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = '0'

    @classmethod
    def endorse_contracts(cls, contracts, endorsement_definition, origin=None):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        endorsements = []
        for contract in contracts:
            date = (origin.effective_date if (origin and origin.effective_date)
                else contract.start_date)
            endorsement = Endorsement(definition=endorsement_definition,
                effective_date=date)
            endorsements.append(endorsement)
            contract_endorsement = ContractEndorsement(
                endorsement=endorsement, contract=contract)
            endorsement.contract_endorsements = [contract_endorsement]
        for endorsement in endorsements:
            endorsement.generated_by = origin
        cls.save(endorsements)
        return endorsements

    @classmethod
    @model.CoopView.button_action('endorsement.act_resume_endorsement')
    def start_endorsement(cls, endorsements):
        pass


class EndorsementContract(values_mixin('endorsement.contract.field'),
        model.CoopSQL, model.CoopView):
    'Endorsement Contract'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'
    _func_key = 'func_key'

    activation_history = fields.One2Many(
        'endorsement.contract.activation_history', 'contract_endorsement',
        'Activation Historry', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'contract', 'definition'], delete_missing=True,
        context={'definition': Eval('definition')})
    extra_datas = fields.One2Many('endorsement.contract.extra_data',
        'contract_endorsement', 'Extra Datas', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'], delete_missing=True,
        context={'definition': Eval('definition')})
    contacts = fields.One2Many('endorsement.contract.contact',
        'contract_endorsement', 'Contacts', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'], delete_missing=True,
        context={'definition': Eval('definition')})
    contract = fields.Many2One('contract', 'Contract', required=True,
        states={'readonly': Eval('state') == 'applied'}, depends=['state'],
        ondelete='CASCADE', select=True)
    endorsement = fields.Many2One('endorsement', 'Endorsement', required=True,
        ondelete='CASCADE', select=True)
    options = fields.One2Many('endorsement.contract.option',
        'contract_endorsement', 'Options', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'contract', 'definition'], delete_missing=True,
        context={'definition': Eval('definition')})
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    endorsement_summary = fields.Function(
        fields.Text('Endorsement Summary'),
        'get_endorsement_summary')
    state = fields.Function(
        fields.Selection([
                ('draft', 'Draft'),
                ('applied', 'Applied'),
                ], 'State'),
        'get_state', searcher='search_state')
    state_string = state.translated('state')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key')

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._error_messages.update({
                'not_latest_applied': ('Endorsement "%s" is not the latest '
                    'applied.'),
                'process_in_progress': ('Contract %s is currently locked in '
                    'process %s.'),
                'only_one_endorsement_in_progress': 'There may only be one '
                'endorsement in_progress at a given time per contract',
                'mes_option_modifications':
                'Options Modifications',
                'mes_activation_history_modifications':
                'Activation History Modifications',
                'mes_extra_data_modifications':
                'Extra Datas Modifications',
                'mes_contact_modifications': 'Contacts Modifications',
                'status_incompatible': 'The status %s of contract %s does not '
                'allow endorsements.',
                })
        cls.values.states = {
            'readonly': Eval('state') == 'applied',
            }
        cls.values.domain = [('definitions', 'in', [Eval('definition')])]
        cls.values.depends = ['state', 'definition']

    def get_func_key(self, name):
        return self.contract.contract_number

    @staticmethod
    def default_state():
        return 'draft'

    @property
    def base_instance(self):
        if not self.contract:
            return None
        if not self.endorsement.rollback_date:
            return self.contract
        with Transaction().set_context(
                _datetime=self.endorsement.rollback_date,
                _datetime_exclude=True):
            return Pool().get('contract')(self.contract.id)

    def get_definition(self, name):
        return self.endorsement.definition.id if self.endorsement else None

    def get_endorsement_summary(self, name):
        result = ['definition_section', self.definition.name, []]
        contract_summary = self.get_summary('contract', self.base_instance)

        if contract_summary:
            result[2] += ['contract_change_section', contract_summary]

        option_summary = [x.get_summary('contract.option', x.option)
            for x in self.options]
        if option_summary:
            result[2] += ['option_change_section',
                '%s :' % self.raise_user_error(
                    'mes_option_modifications', raise_exception=False),
                option_summary]

        activation_summary = [x.get_summary(
                'contract.activation_history', x.activation_history)
            for x in self.activation_history]
        if activation_summary:
            result[2] += ['activation_change_section',
                '%s :' % self.raise_user_error(
                    'mes_activation_history_modifications',
                    raise_exception=False), activation_summary]

        extra_data_summary = [x.get_summary('contract.extra_data',
                x.extra_data) for x in self.extra_datas]
        if extra_data_summary:
            result[2] += ['extra_data_change_section',
                '%s :' % self.raise_user_error(
                    'mes_extra_data_modifications', raise_exception=False),
                extra_data_summary]

        contact_summary = [x.get_summary('contract.contact', x.contact)
            for x in self.contacts]
        if contact_summary:
            result[2] += ['contact_change_section',
                '%s :' % self.raise_user_error(
                    'mes_contact_modifications', raise_exception=False),
                contact_summary]

        return result

    def get_state(self, name):
        return self.endorsement.state if self.endorsement else 'draft'

    @classmethod
    def search_state(cls, name, clause):
        return [('endorsement.state',) + tuple(clause[1:])]

    @classmethod
    def _get_restore_history_order(cls):
        return ['contract', 'contract.activation_history', 'contract.option',
            'contract.extra_data', 'contract.option.version']

    def do_restore_history(self):
        pool = Pool()
        models_to_restore = self._get_restore_history_order()
        restore_dict = {x: [] for x in models_to_restore}
        restore_dict['contract'] += [self.contract, self.base_instance]
        self._prepare_restore_history(restore_dict,
            self.endorsement.rollback_date)

        for model_name in models_to_restore:
            if not restore_dict[model_name]:
                continue
            all_ids = list(set([x.id for x in restore_dict[model_name]]))
            pool.get(model_name).restore_history_before(all_ids,
                self.endorsement.rollback_date)
            utils.clear_transaction_cache(model_name, all_ids)

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        for contract in instances['contract']:
            instances['contract.option'] += contract.options
            instances['contract.activation_history'] += \
                contract.activation_history
            instances['contract.extra_data'] += \
                contract.extra_datas
        for option in contract.options:
            instances['contract.option.version'] += option.versions

    @classmethod
    def draft(cls, contract_endorsements):
        for contract_endorsement in contract_endorsements:
            latest_applied, = cls.search([
                    ('contract', '=', contract_endorsement.contract.id),
                    ('state', 'in', ('applied', 'in_progress')),
                    ], order=[('applied_on', 'DESC')], limit=1)
            if latest_applied != contract_endorsement:
                cls.raise_user_error('not_latest_applied',
                    contract_endorsement.rec_name)

            contract = contract_endorsement.contract
            if contract.current_state and (
                    contract_endorsement.endorsement.state != 'in_progress'):
                cls.raise_user_warning('Process in progress',
                    'process_in_progress', (contract.rec_name,
                        contract.current_state.process.fancy_name))

            contract_endorsement.do_restore_history()
            contract_endorsement.set_applied_on(None)
            contract_endorsement.state = 'draft'
            contract_endorsement.save()

    @classmethod
    def apply(cls, contract_endorsements):
        pool = Pool()
        Contract = pool.get('contract')
        for contract_endorsement in contract_endorsements:
            contract = contract_endorsement.contract
            if contract.status in STATUS_INCOMPATIBLE_WITH_ENDORSEMENTS:
                cls.raise_user_error('status_incompatible',
                    (contract.status, contract.rec_name))
            if contract.current_state and (
                    contract_endorsement.endorsement.state != 'in_progress'):
                cls.raise_user_warning('Process in progress',
                    'process_in_progress', (contract.rec_name,
                        contract.current_state.process.fancy_name))
            if contract_endorsement.endorsement.rollback_date:
                contract_endorsement.set_applied_on(
                    contract_endorsement.endorsement.rollback_date)
            else:
                contract_endorsement.set_applied_on(CurrentTimestamp())
            contract_endorsement.clean_up_before_write()
            values = contract_endorsement.apply_values()
            Contract.write([contract], values)
            contract_endorsement.save()

    def clean_up_before_write(self):
        if self.extra_datas:
            self.clean_up_extra_datas_before_write()

    def clean_up_extra_datas_before_write(self):
        # If we added an extra_data at contract start date
        # we instead update the old extra_data without date
        new_start_date = self.values.get('start_date', None)
        if not new_start_date:
            return
        new_extra_data_at_start_date = [x for x in self.extra_datas if
            x.values.get('date', None) == new_start_date and x.action == 'add']
        if not new_extra_data_at_start_date:
            return
        assert len(new_extra_data_at_start_date) == 1
        new_extra_data_at_start_date = new_extra_data_at_start_date[0]
        extra_datas_without_date = [e for e in self.contract.extra_datas
            if not e.date]
        if not extra_datas_without_date:
            return
        old_extra_data = extra_datas_without_date[0]
        new_extra_data_at_start_date.values['date'] = None
        new_extra_data_at_start_date.action = 'update'
        new_extra_data_at_start_date.relation = old_extra_data.id
        new_extra_data_at_start_date.extra_data = old_extra_data
        self.extra_datas = self.extra_datas

    @classmethod
    def check_in_progress_unicity(cls, contract_endorsements):
        count = Pool().get('endorsement').search_count([
                ('contracts', 'in', [x.contract.id for x in
                        contract_endorsements]),
                ('state', '=', 'in_progress')])
        if count:
            cls.raise_user_error('only_one_endorsement_in_progress')

    def apply_values(self):
        values = super(EndorsementContract, self).apply_values()
        options, activation_history, extra_datas, contacts = [], [], [], []
        for option in self.options:
            options.append(option.apply_values())
        if options:
            values['options'] = options
        for activation_entry in self.activation_history:
            activation_history.append(activation_entry.apply_values())
        if activation_history:
            values['activation_history'] = activation_history
        for extra_data in self.extra_datas:
            extra_datas.append(extra_data.apply_values())
        if extra_datas:
            values['extra_datas'] = extra_datas
        for contact in self.contacts:
            contacts.append(contact.apply_values())
        if contacts:
            values['contacts'] = contacts
        return values

    @property
    def new_activation_history(self):
        elems = set([x for x in self.contract.activation_history])
        for elem in getattr(self, 'activation_history', []):
            if elem.action == 'add':
                elems.add(elem)
            elif elem.action == 'remove':
                elems.remove(elem.option)
            else:
                elems.remove(elem.option)
                elems.add(elem)
        return elems

    @property
    def new_options(self):
        elems = set([x for x in self.contract.options])
        for elem in getattr(self, 'options', []):
            if elem.action == 'add':
                elems.add(elem)
            elif elem.action == 'remove':
                elems.remove(elem.option)
            else:
                elems.remove(elem.option)
                elems.add(elem)
        return elems

    @property
    def new_extra_datas(self):
        elems = set([x for x in self.contract.extra_datas])
        for elem in getattr(self, 'extra_datas', []):
            if elem.action == 'add':
                elems.add(elem)
            elif elem.action == 'remove':
                elems.remove(elem.extra_data)
            else:
                elems.remove(elem.extra_data)
                elems.add(elem)
        return elems

    @property
    def updated_struct(self):
        EndorsementOption = Pool().get('endorsement.contract.option')
        EndorsementExtraData = Pool().get('endorsement.contract.extra_data')
        options, activation_history, extra_datas = {}, {}, {}
        for option in self.new_options:
            options[option] = EndorsementOption.updated_struct(option)
        for activation_entry in self.new_activation_history:
            activation_history[activation_entry] = \
                EndorsementActivationHistory.updated_struct(activation_entry)
        for extra_data in self.new_extra_datas:
            extra_datas[extra_data] = EndorsementExtraData.updated_struct(
                extra_data)
        return {
            'activation_history': activation_history,
            'options': options,
            'extra_datas': extra_datas,
            }

    def get_endorsed_record(self):
        return self.contract

    @classmethod
    def _export_light(cls):
        return (super(EndorsementContract, cls)._export_light() |
            set(['contract']))

    @classmethod
    def add_func_key(cls, values):
        if 'contract' in values and '_func_key' in values['contract']:
            values['_func_key'] = values['contract']['_func_key']
        else:
            values['_func_key'] = 0

    @classmethod
    def new_rollback_point(cls, contracts, at_date, definition,
            init_dict=None):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        if isinstance(definition, basestring):
            Definition = pool.get('endorsement.definition')
            definition = Definition.search([('xml_id', '=', definition)])[0]
        init_dict = init_dict or {}
        endorsement = Endorsement()
        contract_endorsements = []
        for contract in contracts:
            contract_endorsements.append(ContractEndorsement(
                    contract=contract, applied_on=datetime.datetime.now(),
                    **init_dict))
        endorsement.contract_endorsements = contract_endorsements
        endorsement.effective_date = at_date
        endorsement.state = 'applied'
        endorsement.applied_by = Transaction().user
        endorsement.rollback_date = CurrentTimestamp()
        endorsement.application_date = datetime.datetime.now()
        endorsement.definition = definition
        return endorsement


class EndorsementOption(relation_mixin(
            'endorsement.contract.option.field', 'option', 'contract.option',
            'Options'),
        model.CoopSQL, model.CoopView):
    'Endorsement Option'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.option'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    versions = fields.One2Many('endorsement.contract.option.version',
        'option_endorsement', 'Versions Endorsements', delete_missing=True)
    coverage = fields.Function(
        fields.Many2One('offered.option.description', 'Coverage'),
        'on_change_with_coverage')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    manual_start_date = fields.Function(
        fields.Date('Start Date'),
        '')
    manual_end_date = fields.Function(
        fields.Date('End Date'),
        '')

    @classmethod
    def __setup__(cls):
        super(EndorsementOption, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_coverage': 'New Coverage: %s',
                'mes_versions_modification': 'Versions Modifications',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    @fields.depends('values', 'option')
    def on_change_with_coverage(self, name=None):
        result = self.values.get('coverage', None)
        if result:
            return result
        if self.option:
            return self.option.coverage.id

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    def get_rec_name(self, name):
        if self.option:
            return self.option.rec_name
        return '%s : %s' % (self.raise_user_error('new_coverage',
                raise_exception=False), self.coverage.rec_name)

    def apply_values(self):
        values = super(EndorsementOption, self).apply_values()
        version_values = []
        for version in self.versions:
            version_values.append(version.apply_values())
        if version_values:
            if self.action == 'add':
                values[1][0]['versions'] = version_values
            elif self.action == 'update':
                values[2]['versions'] = version_values
        return values

    def get_summary(self, model, base_object=None):
        result = super(EndorsementOption, self).get_summary(model,
            base_object)
        if self.action == 'remove':
            return result
        option_summary = [x.get_summary('contract.option.version', x.version)
            for x in self.versions]
        if option_summary:
            result.append(['option_version_change_section', '%s :' % (
                        self.raise_user_error('mes_option_modifications',
                            raise_exception=False)), option_summary])
        return result

    @classmethod
    def updated_struct(cls, option):
        return {}

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'contract'}


class EndorsementOptionVersion(relation_mixin(
            'endorsement.contract.option.version.field', 'version',
            'contract.option.version', 'Versions'),
        model.CoopSQL, model.CoopView):
    'Endorsement Option Version'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.option.version'

    option_endorsement = fields.Many2One('endorsement.contract.option',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    extra_data = fields.Dict('extra_data', 'Extra Data')

    @classmethod
    def __setup__(cls):
        super(EndorsementOptionVersion, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_option_version': 'New Option Version',
                })
        cls._endorsed_dicts = {'extra_data': 'extra_data'}

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.option_endorsement.definition.id

    def get_rec_name(self, name):
        return '%s' % (self.raise_user_error('new_option_version',
                raise_exception=False))

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'option'}


class EndorsementActivationHistory(relation_mixin(
            'endorsement.contract.activation_history.field',
            'activation_history', 'contract.activation_history',
            'Activation History'),
        model.CoopSQL, model.CoopView):
    'Endorsement Activation History'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.activation_history'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    @classmethod
    def updated_struct(cls, activation_history):
        return {}


class EndorsementContact(relation_mixin(
            'endorsement.contract.contact.field',
            'contact', 'contract.contact',
            'Contract Contacts'),
        model.CoopSQL, model.CoopView):
    'Endorsement Contact'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.contact'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    @classmethod
    def updated_struct(cls, activation_history):
        return {}

    @classmethod
    def _ignore_fields_for_matching(cls):
        return super(EndorsementContact,
            cls)._ignore_fields_for_matching() | {'contract'}


class EndorsementExtraData(relation_mixin(
            'endorsement.contract.extra_data.field', 'extra_data',
            'contract.extra_data', 'Extra Datas'),
        model.CoopSQL, model.CoopView):
    'Endorsement Extra Data'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.extra_data'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    new_extra_data_values = fields.Dict('extra_data', 'Extra Data Values')
    new_extra_data_values_string = new_extra_data_values.translated(
        'extra_data_values')

    @classmethod
    def __setup__(cls):
        super(EndorsementExtraData, cls).__setup__()
        cls._error_messages.update({
                'new_extra_data': 'New Extra Data',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    def get_rec_name(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        lang = pool.get('res.user')(Transaction().user).language
        if self.extra_data:
            if self.extra_data.date:
                return Date.date_as_string(self.extra_data.date, lang)
            return ''
        else:
            return self.raise_user_error('new_extra_data',
                raise_exception=False)

    @classmethod
    def updated_struct(cls, extra_data):
        return {}

    def apply_values(self):
        apply_values = super(EndorsementExtraData, self).apply_values()
        if self.action == 'add':
            values = apply_values[1][0]
            if not values.get('extra_data_values'):
                values['extra_data_values'] = dict(self.new_extra_data_values)
            apply_values = ('create', [values])
        elif self.action == 'update':
            values = apply_values[2]
            values['extra_data_values'] = dict(self.new_extra_data_values)
            apply_values = ('write', apply_values[1], values)
        return apply_values

    def get_summary(self, model, base_object=None):
        endorsement_state = self.contract_endorsement.endorsement.state
        # We want to present each extra data entry like a field
        new_data_values = self.values.pop('extra_data_values', None)
        res = super(EndorsementExtraData, self).get_summary(model, base_object)
        self.values['extra_data_values'] = new_data_values
        if not new_data_values:
            new_data_values = self.new_extra_data_values
        if self.action == 'update' and self.extra_data and \
                self.extra_data.extra_data_values:
            cur_data_values = self.extra_data.extra_data_values
        else:
            cur_data_values = None

        if not res[2]:
            res[2] = []
        if cur_data_values and not endorsement_state == 'applied':
            for k, v in cur_data_values.iteritems():
                if new_data_values[k] != v:
                    res[2].append(k + ': ' + str(v) + u' → ' + str(
                            new_data_values[k]))
        else:
            for k, v in new_data_values.iteritems():
                res[2].append(k + ': ' + u' → ' + str(v))
        return res

    def is_null(self):
        return super(EndorsementExtraData, self).is_null() and not \
            self.new_extra_data_values


class Configuration(ModelSingleton, model.CoopSQL, model.CoopView):
    'Endorsement Configuration'
    __name__ = 'endorsement.configuration'

    endorsement_number_sequence = fields.Property(
        fields.Many2One('ir.sequence', 'Endorsement Number Sequence'))


class ReportTemplate:
    __name__ = 'report.template'
    __metaclass__ = PoolMeta

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if self.on_model and self.on_model.model == 'endorsement':
            result.append(('endorsement', 'Endorsement'))
        return result

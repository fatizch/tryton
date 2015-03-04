# encoding: utf-8
import copy
import datetime
from sql.functions import Now

from trytond.error import UserError
from trytond.rpc import RPC
from trytond.pool import PoolMeta
from trytond.model import Workflow, Model, fields as tryton_fields, \
    ModelSingleton
from trytond.pyson import Eval, PYSONEncoder, PYSON, Bool, Len, Or
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields, coop_string, utils
from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework

_STATES_WITH_SUBSTATES = ['declined']

__all__ = [
    'field_mixin',
    'values_mixin',
    'relation_mixin',
    'Contract',
    'ContractOption',
    'ContractExtraData',
    'ContractActivationHistory',
    'Endorsement',
    'EndorsementContract',
    'EndorsementOption',
    'EndorsementActivationHistory',
    'EndorsementExtraData',
    'Configuration',
    ]


def field_mixin(model):

    class Mixin(Model):
        name = fields.Function(fields.Char('Name'), 'get_name',
            searcher='search_name')
        endorsement_part = fields.Many2One('endorsement.part',
            'Endorsement Part', states={'invisible': True},
            ondelete='CASCADE')
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

    return Mixin


def values_mixin(value_model):

    class Mixin(model.CoopSQL, model.CoopView):
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
                        'depends': (['values', 'applied_on']
                            + cls.values.depends),
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

        def get_summary(self, model, base_object=None, indent=0, increment=2):
            pool = Pool()
            Date = pool.get('ir.date')
            lang = pool.get('res.user')(Transaction().user).language
            ValueModel = pool.get(model)
            vals = []
            if not self.values:
                return ''
            for k, v in self.values.iteritems():
                prev_value = getattr(base_object, k, '') if (base_object and
                    hasattr(base_object, k)) else ''
                field = ValueModel._fields[k]
                if isinstance(field, tryton_fields.Many2One):
                    if v:
                        vals.append((k, field,
                                prev_value.rec_name if prev_value else '',
                                pool.get(field.model_name)(v).rec_name))
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
                    vals.append((k, field, prev_value, v))
            return '\n'.join([' ' * indent + u'%s : %s → %s' % (
                        coop_string.translate(
                            ValueModel, fname, ffield.string, 'field'),
                        old, new) for fname, ffield, old, new in vals
                    if old != new])

    return Mixin


def relation_mixin(value_model, field, model, name):

    class Mixin(values_mixin(value_model)):
        _func_key = 'func_key'

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

        @classmethod
        def read(cls, ids, fields_names=None):
            BaseModel = Pool().get(model)
            relation_fields_to_read = [fname for fname in fields_names
                if isinstance(cls._fields[fname], tryton_fields.Function)
                and fname in BaseModel._fields and
                not cls._fields[fname].getter]
            if relation_fields_to_read:
                result = super(Mixin, cls).read(ids, list(set(fields_names) -
                        set(relation_fields_to_read)) + ['relation', 'values'])
            else:
                return super(Mixin, cls).read(ids, fields_names)

            relation_values = BaseModel.read([x['relation'] for x in result
                    if x['relation']], relation_fields_to_read)
            relation_values = {x['id']: x for x in relation_values}
            for row in result:
                if 'values' not in row or not row['relation']:
                    row[fname] = None
                for fname in relation_fields_to_read:
                    if 'values' in row and fname in row['values']:
                        row[fname] = row['values'][fname]
                    else:
                        row[fname] = relation_values[row['relation']][fname]
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
                            target.export_json(output=export)
                            new_values_field[key] = export[-1]
                        else:
                            new_values_field[key] = value
                    values['values'] = new_values_field
            return values

        def apply_values(self):
            values = (self.values if self.values else {}).copy()
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
            return utils.get_history_instance(model, self.relation,
                self.applied_on)

        def get_summary(self, model, base_object=None, indent=0, increment=2):
            if self.action == 'remove':
                return ' ' * indent + '%s %s' % (self.raise_user_error(
                        'mes_remove_version', raise_exception=False),
                    self.base_instance.rec_name)
            elif self.action == 'add':
                result = ' ' * indent + '%s:\n' % self.raise_user_error(
                    'mes_new_version', raise_exception=False)
                result += super(Mixin, self).get_summary(model, base_object,
                    indent + increment, increment)
                return result
            elif self.action == 'update':
                result = ' ' * indent + '%s:\n' % self.raise_user_error(
                    'mes_update_version', (base_object.rec_name),
                    raise_exception=False)
                result += super(Mixin, self).get_summary(model, base_object,
                    indent + increment, increment)
                return result
            return super(Mixin, self).get_summary(model, base_object, indent,
                increment)

        def get_func_key(self, name):
            return getattr(self, field).func_key if getattr(self, field) \
                else ''

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

    def get_latest_endorsement(self, name):
        Endorsement = Pool().get('endorsement')
        endorsement = Endorsement.search([
                ('contracts', '=', self.id),
                ('state', 'not in', ['draft', 'canceled', 'declined']),
                ], order=[('application_date', 'DESC')], limit=1)
        if endorsement:
            return endorsement[0].id

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
        self.set_start_date(caller.values['start_date'])
        self.save()

    def calculate_after_endorsement(self, caller=None):
        self.calculate()
        if caller.__name__ == 'endorsement.contract':
            if 'end_date' in caller.values:
                self.set_and_propagate_end_date(caller.values['end_date'])
            self.save()

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        # Create endorsements for rollback points BEFORE super
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        endorsement = ContractEndorsement.new_rollback_point(contracts,
            at_date, {'values': {
                    'status': 'terminated',
                    'sub_status': termination_reason.id,
                    'end_date': at_date,
                    }})
        endorsement.save()

        super(Contract, cls).terminate(contracts, at_date, termination_reason)

    @classmethod
    def void(cls, contracts, void_reason):
        # Create endorsements for rollback points BEFORE super
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        endorsement = ContractEndorsement.new_rollback_point(contracts,
            contracts[0].start_date, {'values': {
                    'status': 'void',
                    'sub_status': void_reason.id,
                    }})
        endorsement.save()

        super(Contract, cls).void(contracts, void_reason)


class ContractOption(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.option'


class ContractActivationHistory(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.activation_history'


class ContractExtraData(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.extra_data'


class Endorsement(Workflow, model.CoopSQL, model.CoopView):
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
        fields.Text('Endorsement Summary'),
        'get_endorsement_summary')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments')
    contracts_name = fields.Function(
        fields.Char('Contracts Name'),
        'get_contracts_name')
    subscribers_name = fields.Function(
        fields.Char('Subscribers Name'),
        'get_subscribers_name')

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
                ('canceled', 'applied'),
                ('canceled', 'in_progress'),
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
        cls._sql_constraints = [
            ('number_uniq', 'UNIQUE(number)',
                'The endorsement number must be unique.')
        ]

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

    def get_contracts_name(self, name):
        return '\n'.join([x.rec_name for x in self.contracts])

    def get_subscribers_name(self, name):
        return '\n'.join([x.subscriber.rec_name for x in self.contracts])

    @fields.depends('state')
    def on_change_with_sub_state_required(self, name=None):
        return self.state in _STATES_WITH_SUBSTATES

    def get_contracts(self, name):
        return [x.contract.id for x in self.contract_endorsements]

    def get_endorsement_summary(self, name):
        result = '\n\n'.join([x.get_endorsement_summary(name)
                for x in self.all_endorsements()])
        return result

    @classmethod
    def search_contracts(cls, name, clause):
        return [('contract_endorsements.contract',) + tuple(clause[1:])]

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

    @classmethod
    @model.CoopView.button
    @Workflow.transition('canceled')
    def cancel(cls, endorsements):
        cls._draft(endorsements)
        cls.write(endorsements, {
                'rollback_date': None,
                'state': 'canceled',
                })

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
        cls.write(endorsements, {'rollback_date': Now()})

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
            ModelClass.apply(endorsements_per_model[model_name])
        set_rollback, do_not_set_rollback = [], []
        for endorsement in endorsements:
            if endorsement.rollback_date:
                do_not_set_rollback.append(endorsement)
            else:
                set_rollback.append(endorsement)
        if set_rollback:
            cls.write(set_rollback, {
                    'applied_by': Transaction().user,
                    'rollback_date': Now(),
                    'application_date': datetime.datetime.now(),
                    })
        if do_not_set_rollback:
            cls.write(do_not_set_rollback, {
                    'applied_by': Transaction().user,
                    'application_date': datetime.datetime.now(),
                    })

        # Force reload endorsement list
        for idx, endorsement in enumerate(cls.browse(
                    [x.id for x in endorsements])):
            endorsements[idx] = endorsement
        endorsements_per_model = cls.group_per_model(endorsements)
        for model_name in cls.apply_order():
            for endorsement in endorsements_per_model.get(model_name, []):
                instance = endorsement.get_endorsed_record()
                methods = endorsement.definition.get_methods_for_model(
                    instance.__name__)
                for method in methods:
                    method.execute(endorsement, instance)
                instance.save()
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
    @model.CoopView.button_action('endorsement.act_decline_endorsement')
    def button_decline_endorsement(cls, endorsements):
        pass

    @classmethod
    def soft_apply(cls, endorsements):
        with Transaction().set_context(endorsement_soft_apply=True):
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
                applied_self = self.__class__(self.id)
                self.apply_for_preview([applied_self])
                for unitary_endorsement in applied_self.all_endorsements():
                    endorsed_record = unitary_endorsement.get_endorsed_record()
                    endorsed_model, endorsed_id = (endorsed_record.__name__,
                        endorsed_record.id)
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
    contract = fields.Many2One('contract', 'Contract', required=True,
        states={'readonly': Eval('state') == 'applied'}, depends=['state'],
        ondelete='CASCADE')
    endorsement = fields.Many2One('endorsement', 'Endorsement', required=True,
        ondelete='CASCADE')
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
                })
        cls.values.states = {
            'readonly': Eval('state') == 'applied',
            }
        cls.values.domain = [('definition', '=', Eval('definition'))]
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
        result = self.definition.name + ':\n'
        contract_summary = self.get_summary('contract', self.base_instance, 2)
        if contract_summary:
            result += contract_summary
            result += '\n\n'
        option_summary = '\n'.join([option.get_summary('contract.option',
                    option, indent=4)
                for option in self.options])
        if option_summary:
            result += '  Option modifications :\n'
            result += option_summary
            result += '\n\n'
        activation_summary = '\n'.join([activation_history.get_summary(
                    'contract.activation_history', indent=4)
                for activation_history in self.activation_history])
        if activation_summary:
            result += '  Activation modifications :\n'
            result += activation_summary
            result += '\n\n'
        extra_data_summary = '\n'.join([extra_data.get_summary(
                    'contract.extra_data', extra_data,
                    indent=4)
                for extra_data in self.extra_datas])
        if extra_data_summary:
            result += '  Extra Data modifications :\n'
            result += extra_data_summary
            result += '\n\n'
        return result

    def get_state(self, name):
        return self.endorsement.state if self.endorsement else 'draft'

    @classmethod
    def search_state(cls, name, clause):
        return [('endorsement.state',) + tuple(clause[1:])]

    @classmethod
    def _get_restore_history_order(cls):
        return ['contract', 'contract.activation_history', 'contract.option',
            'contract.extra_data']

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
            pool.get(model_name).restore_history_before(
                list(set([x.id for x in restore_dict[model_name]])),
                self.endorsement.rollback_date)

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        for contract in instances['contract']:
            instances['contract.option'] += contract.options
            instances['contract.activation_history'] += \
                contract.activation_history
            instances['contract.extra_data'] += \
                contract.extra_datas

    @classmethod
    def draft(cls, contract_endorsements):
        for contract_endorsement in contract_endorsements:
            latest_applied, = cls.search([
                    ('contract', '=', contract_endorsement.contract.id),
                    ('state', '!=', 'draft'),
                    ], order=[('applied_on', 'DESC')], limit=1)
            if latest_applied != contract_endorsement:
                cls.raise_user_error('not_latest_applied',
                    contract_endorsement.rec_name)

            contract = contract_endorsement.contract
            if contract.current_state and (
                    contract_endorsement.endorsement.state != 'in_progress'):
                cls.raise_user_error('process_in_progress', (
                        contract.rec_name,
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
            if contract.current_state and (
                    contract_endorsement.endorsement.state != 'in_progress'):
                cls.raise_user_error('process_in_progress', (
                        contract.rec_name,
                        contract.current_state.process.fancy_name))
            if contract_endorsement.endorsement.rollback_date:
                contract_endorsement.set_applied_on(
                    contract_endorsement.endorsement.rollback_date)
            else:
                contract_endorsement.set_applied_on(contract.write_date
                    or contract.create_date)
            values = contract_endorsement.apply_values()
            Contract.write([contract], values)
            contract_endorsement.save()

    @classmethod
    def check_in_progress_unicity(cls, contract_endorsements):
        count = Pool().get('endorsement').search_count([
                ('contracts', 'in', [x.contract.id for x in
                        contract_endorsements]),
                ('state', '=', 'in_progress')])
        if count:
            cls.raise_user_error('only_one_endorsement_in_progress')

    def set_applied_on(self, at_datetime):
        self.applied_on = at_datetime
        for option in self.options:
            option.applied_on = at_datetime
        self.options = list(self.options)

    def apply_values(self):
        values = (self.values if self.values else {}).copy()
        options, activation_history, extra_datas = [], [], []
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
    def new_rollback_point(cls, contracts, at_date, init_dict=None):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        Definition = pool.get('endorsement.definition')
        init_dict = init_dict or {}
        endorsement = Endorsement()
        contract_endorsements = []
        for contract in contracts:
            contract_endorsements.append(ContractEndorsement(
                    contract=contract, **init_dict))
        endorsement.contract_endorsements = contract_endorsements
        endorsement.effective_date = at_date
        endorsement.state = 'applied'
        endorsement.applied_by = Transaction().user
        endorsement.rollback_date = Now()
        endorsement.application_date = datetime.datetime.now()
        endorsement.definition = Definition.search([
                ('xml_id', '=', 'endorsement.stop_contract_definition')])[0]
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
    coverage = fields.Function(
        fields.Many2One('offered.option.description', 'Coverage'),
        'on_change_with_coverage')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementOption, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_coverage': 'New Coverage: %s',
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

    @classmethod
    def updated_struct(cls, option):
        return {}


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
            values['extra_data_values'] = dict(self.new_extra_data_values)
            apply_values = ('create', [values])
        elif self.action == 'update':
            values = apply_values[2]
            values['extra_data_values'] = dict(self.new_extra_data_values)
            apply_values = ('write', apply_values[1], values)
        return apply_values

    def get_summary(self, model, base_object=None, indent=0, increment=2):
        res = super(EndorsementExtraData, self).get_summary(model, base_object,
            indent, increment) + '\n'
        indent += 2
        new_data_values = self.new_extra_data_values
        if self.extra_data and self.extra_data.extra_data_values:
            cur_data_values = self.extra_data.extra_data_values
        else:
            cur_data_values = None

        if cur_data_values:
            for k, v in cur_data_values.iteritems():
                if new_data_values[k] != v:
                    res += ' ' * indent + k + ': ' + str(v) + u' → ' + str(
                        new_data_values[k]) + '\n'
        else:
            for k, v in new_data_values.iteritems():
                res += ' ' * indent + k + ': ' + u' → ' + str(v) + '\n'
        return res


class Configuration(ModelSingleton, model.CoopSQL, model.CoopView):
    'Endorsement Configuration'
    __name__ = 'endorsement.configuration'

    endorsement_number_sequence = fields.Property(
        fields.Many2One('ir.sequence', 'Endorsement Number Sequence'))

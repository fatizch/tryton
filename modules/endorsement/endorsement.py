# encoding: utf-8
import copy
import datetime

from trytond.pool import PoolMeta
from trytond.rpc import RPC
from trytond.model import Workflow, Model, fields as tryton_fields
from trytond.pyson import Eval, PYSONEncoder, PYSON
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields, coop_string, utils


__all__ = [
    'field_mixin',
    'values_mixin',
    'relation_mixin',
    'Contract',
    'ContractOption',
    'ContractActivationHistory',
    'Endorsement',
    'EndorsementContract',
    'EndorsementOption',
    'EndorsementActivationHistory',
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
                ])
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
                        ('endorsement_parts', '=', self.template.id)])]

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
            ValueModel = pool.get(model)
            vals = []
            if not self.values:
                return ''
            for k, v in self.values.iteritems():
                prev_value = getattr(base_object, k, '') if base_object else ''
                field = ValueModel._fields[k]
                if isinstance(field, tryton_fields.Many2One):
                    if v:
                        vals.append((k, field,
                                prev_value.rec_name if prev_value else '',
                                pool.get(field.model_name)(v).rec_name))
                    else:
                        vals.append((k, field,
                                prev_value.rec_name if prev_value else '', ''))
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

        @property
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
                    self.base_instance.date)
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

    setattr(Mixin, field, fields.Function(fields.Many2One(model, name,
                datetime_field='applied_on',
                states={
                    'required': Eval('action').in_(['update', 'remove']),
                    'invisible': Eval('action') == 'add',
                    },
                depends=['action']),
            'get_relation', setter='set_relation'))

    return Mixin


class Contract(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'revert_last_endorsement': {},
                })

    @classmethod
    @model.CoopView.button
    def revert_last_endorsement(cls, contracts):
        Endorsement = Pool().get('endorsement')
        endorsements_to_cancel = set()
        for contract in contracts:
            last_endorsement = Endorsement.search([
                    ('contracts', '=', contract.id),
                    ('state', '=', 'applied'),
                    ], order=[('application_date', 'DESC')], limit=1)
            if last_endorsement:
                endorsements_to_cancel.add(last_endorsement[0])
        if endorsements_to_cancel:
            Endorsement.draft(list(endorsements_to_cancel))
        return 'close'

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


class ContractOption(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.option'


class ContractActivationHistory(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.activation_history'


class Endorsement(Workflow, model.CoopSQL, model.CoopView):
    'Endorsement'

    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    applicant = fields.Many2One('party.party', 'Applicant')
    application_date = fields.DateTime('Application Date', readonly=True,
        states={'invisible': Eval('state', '') == 'draft'},
        depends=['state'])
    applied_by = fields.Many2One('res.user', 'Applied by', readonly=True,
        states={'invisible': Eval('state', '') == 'draft'},
        depends=['state'])
    contract_endorsements = fields.One2Many('endorsement.contract',
        'endorsement', 'Contract Endorsement')
    definition = fields.Many2One('endorsement.definition', 'Definition',
        required=True)
    effective_date = fields.Date('Effective Date')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('applied', 'Applied'),
            ], 'State', readonly=True)
    contracts = fields.Function(
        fields.Many2Many('contract', '', '', 'Contracts'),
        'get_contracts', searcher='search_contracts')
    endorsement_summary = fields.Function(
        fields.Text('Endorsement Summary'),
        'get_endorsement_summary')

    @classmethod
    def __setup__(cls):
        super(Endorsement, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'applied'),
                ('applied', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['applied']),
                    },
                'apply': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'open_contract': {
                    'invisible': ~Eval('state').in_(['applied']),
                    },
                })
        cls._order = [('application_date', 'DESC'), ('create_date', 'DESC')]

    @classmethod
    def default_state(cls):
        return 'draft'

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
        if endorsement_part.kind in ('contract', 'option'):
            return self.contract_endorsements

    def new_endorsement(self, endorsement_part):
        # Return a new endorsement instantiation depending on the endorsement
        # part
        if endorsement_part.kind in ('contract', 'option',
                'activation_history'):
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
    @model.CoopView.button
    @Workflow.transition('draft')
    def draft(cls, endorsements):
        pool = Pool()
        endorsements_per_model = cls.group_per_model(endorsements)
        for model_name in cls.apply_order():
            if model_name not in endorsements_per_model:
                continue
            ModelClass = pool.get(model_name)
            ModelClass.draft(endorsements_per_model[model_name])
        cls.write(endorsements, {'applied_by': None,
                'application_date': None})

    @classmethod
    @model.CoopView.button
    @Workflow.transition('applied')
    def apply(cls, endorsements):
        pool = Pool()
        endorsements_per_model = cls.group_per_model(endorsements)
        for model_name in cls.apply_order():
            if model_name not in endorsements_per_model:
                continue
            ModelClass = pool.get(model_name)
            ModelClass.apply(endorsements_per_model[model_name])
        cls.write(endorsements, {'applied_by': Transaction().user,
                'application_date': datetime.datetime.now()})

        endorsements_per_model = cls.group_per_model(endorsements)
        for model_name in cls.apply_order():
            for endorsement in endorsements_per_model.get(model_name, []):
                instance = endorsement.get_endorsed_record()
                methods = endorsement.definition.get_methods_for_model(
                    instance.__name__)
                for method in methods:
                    method.execute(endorsement, instance)

    @classmethod
    @model.CoopView.button_action('endorsement.act_contract_open')
    def open_contract(cls, endorsements):
        pass

    def extract_preview_values(self, extraction_method):
        pool = Pool()
        current_values, old_values, new_values = {}, {}, {}
        for unitary_endorsement in self.all_endorsements():
            endorsed_record = unitary_endorsement.get_endorsed_record()
            endorsed_model, endorsed_id = (endorsed_record.__name__,
                endorsed_record.id)
            current_values['%s,%i' % (endorsed_model, endorsed_id)] = \
                extraction_method(endorsed_record)
        if self.application_date:
            for unitary_endorsement in self.all_endorsements():
                endorsed_record = unitary_endorsement.get_endorsed_record()
                endorsed_model, endorsed_id = (endorsed_record.__name__,
                    endorsed_record.id)
                old_record = utils.get_history_instance(endorsed_model,
                    endorsed_id, self.application_date)
                old_values['%s,%i' % (endorsed_model, endorsed_id)] = \
                    extraction_method(old_record)
            new_values = current_values
        else:
            # Make sure all changes are saved
            assert not self._save_values

            # Apply endorsement in a sandboxed transaction
            with Transaction().new_cursor():
                applied_self = self.__class__(self.id)
                self.apply([applied_self])
                for unitary_endorsement in applied_self.all_endorsements():
                    endorsed_record = unitary_endorsement.get_endorsed_record()
                    endorsed_model, endorsed_id = (endorsed_record.__name__,
                        endorsed_record.id)
                    record = pool.get(endorsed_model)(endorsed_id)
                    new_values['%s,%i' % (endorsed_model, endorsed_id)] = \
                        extraction_method(record)
                old_values = current_values
                Transaction().cursor.rollback()
            return {'old': old_values, 'new': new_values}


class EndorsementContract(values_mixin('endorsement.contract.field'),
        model.CoopSQL, model.CoopView):
    'Endorsement Contract'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    activation_history = fields.One2Many(
        'endorsement.contract.activation_history', 'contract_endorsement',
        'Activation Historry', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'contract', 'definition'],
        context={'definition': Eval('definition')})
    contract = fields.Many2One('contract', 'Contract', required=True,
        datetime_field='applied_on',
        states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state'])
    endorsement = fields.Many2One('endorsement', 'Endorsement', required=True,
        ondelete='CASCADE')
    options = fields.One2Many('endorsement.contract.option',
        'contract_endorsement', 'Options', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'contract', 'definition'],
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

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._error_messages.update({
                'not_latest_applied': ('Endorsement "%s" is not the latest '
                    'applied.')
                })
        cls.values.states = {
            'readonly': Eval('state') == 'applied',
            }
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['state', 'definition']

    @staticmethod
    def default_state():
        return 'draft'

    @property
    def base_instance(self):
        if not self.contract:
            return None
        if not self.applied_on:
            return self.contract
        return utils.get_history_instance('contract', self.contract.id,
            self.applied_on)

    def get_definition(self, name):
        return self.endorsement.definition.id if self.endorsement else None

    def get_endorsement_summary(self, name):
        result = self.definition.name + ':\n'
        contract_summary = self.get_summary('contract', self.base_instance, 2)
        if contract_summary:
            result += contract_summary
            result += '\n\n'
        option_summary = '\n'.join([option.get_summary('contract.option',
                    indent=4)
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
        return result

    def get_state(self, name):
        return self.endorsement.state if self.endorsement else 'draft'

    @classmethod
    def search_state(cls, name, clause):
        return [('endorsement.state',) + tuple(clause[1:])]

    def _restore_history(self):
        pool = Pool()
        Contract = pool.get('contract')
        ContractOption = pool.get('contract.option')
        ActivationHistory = pool.get('contract.activation_history')

        hcontract = self.contract
        contract = Contract(self.contract.id)

        Contract.restore_history([contract.id], self.applied_on)
        option_ids = set((o.id
                for o in (contract.options + hcontract.options)))
        ContractOption.restore_history(list(option_ids),
            self.applied_on)
        activation_history_ids = set((o.id
                for o in (contract.activation_history +
                    hcontract.activation_history)))
        ActivationHistory.restore_history(list(activation_history_ids),
            self.applied_on)

        return contract, hcontract

    @classmethod
    def draft(cls, contract_endorsements):
        for contract_endorsement in contract_endorsements:
            latest_applied, = cls.search([
                    ('contract', '=', contract_endorsement.contract.id),
                    ('state', '=', 'applied'),
                    ], order=[('applied_on', 'DESC')], limit=1)
            if latest_applied != contract_endorsement:
                cls.raise_user_error('not_latest_applied',
                    contract_endorsement.rec_name)

            contract_endorsement._restore_history()
            contract_endorsement.set_applied_on(None)
            contract_endorsement.state = 'draft'
            contract_endorsement.save()

    @classmethod
    def apply(cls, contract_endorsements):
        pool = Pool()
        Contract = pool.get('contract')
        for contract_endorsement in contract_endorsements:
            contract = contract_endorsement.contract
            contract_endorsement.set_applied_on(contract.write_date
                or contract.create_date)
            values = contract_endorsement.apply_values
            Contract.write([contract], values)
            contract_endorsement.save()

    def set_applied_on(self, at_datetime):
        self.applied_on = at_datetime
        for option in self.options:
            option.applied_on = at_datetime
        self.options = list(self.options)

    @property
    def apply_values(self):
        values = (self.values if self.values else {}).copy()
        options, activation_history = [], []
        for option in self.options:
            options.append(option.apply_values)
        if options:
            values['options'] = options
        for activation_entry in self.activation_history:
            activation_history.append(activation_entry.apply_values)
        if activation_history:
            values['activation_history'] = activation_history
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
    def updated_struct(self):
        EndorsementOption = Pool().get('endorsement.contract.option')
        options, activation_history = {}, {}
        for option in self.new_options:
            options[option] = EndorsementOption.updated_struct(option)
        for activation_entry in self.new_activation_history:
            activation_history[activation_entry] = \
                EndorsementActivationHistory.updated_struct(activation_entry)
        return {
            'activation_history': activation_history,
            'options': options,
            }

    def get_endorsed_record(self):
        return self.contract


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

    def updated_struct(cls, option):
        return {}

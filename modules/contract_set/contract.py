# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.aggregate import Max

from trytond.pool import PoolMeta, Pool
from trytond import backend
from trytond.tools.multivalue import migrate_property
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool, Equal
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import model, fields
from trytond.modules.company.model import (CompanyValueMixin,
    CompanyMultiValueMixin)
from trytond.modules.contract import _STATES, _DEPENDS
from trytond.modules.contract.contract import CONTRACTSTATUSES
from trytond.wizard import StateTransition, StateView, Button
from trytond.modules.report_engine import Printable
from trytond.model.multivalue import filter_pattern

__all__ = [
    'ContractSet',
    'Contract',
    'ContractSetDecline',
    'ContractSetSelectDeclineReason',
    'ReportTemplate',
    'Configuration',
    'ConfigurationContractSetNumberSequence',
    ]


class Configuration(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'offered.configuration'

    contract_set_number_sequence = fields.MultiValue(
        fields.Many2One('ir.sequence', 'Contract Set Number Sequence',
            domain=[('code', '=', 'contract_set_number')]))

    @classmethod
    def default_contract_set_number_sequence(cls, **pattern):
        return cls.multivalue_model(
            'contract_set_number_sequence'
            ).default_contract_set_number_sequence(**pattern)


class ConfigurationContractSetNumberSequence(model.CoogSQL, CompanyValueMixin):
    'Configuration Contract Set Number Sequence'
    __name__ = 'offered.configuration.contract_set_number_sequence'

    configuration = fields.Many2One('offered.configuration', 'Configuration',
        ondelete='CASCADE', select=True)
    contract_set_number_sequence = fields.Many2One('ir.sequence',
        'Contract Set Number Sequence',
        domain=[('code', '=', 'contract_set_number')],
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationContractSetNumberSequence, cls).__register__(
            module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('contract_set_number_sequence')
        value_names.append('contract_set_number_sequence')
        migrate_property(
            'offered.configuration', field_names, cls, value_names,
            parent='configuration', fields=fields)

    @classmethod
    def default_contract_set_number_sequence(cls, **pattern):
        Sequence = Pool().get('ir.sequence')
        pattern = filter_pattern(pattern, Sequence)
        domain = [('code', '=', 'contract_set_number')]
        for key, value in pattern.items():
            domain.append((str(key), '=', value))
        sequences = Sequence.search(domain)
        if len(sequences) == 1:
            return sequences[0].id


class ContractSet(Printable, model.CoogSQL, model.CoogView):
    'Contract Set'

    __name__ = 'contract.set'
    _func_key = 'number'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True)
    contracts = fields.One2Many('contract', 'contract_set', 'Contracts',
        target_not_required=True)
    subscribers = fields.Function(fields.Text('Subscribers'),
        'get_subscribers', searcher='search_subscribers')
    products = fields.Function(fields.Text('Products'),
        'get_products', searcher='search_products')
    contracts_declined = fields.Function(fields.Boolean('Contracts Declined'),
        'get_contracts_declined')
    status = fields.Function(fields.Selection(CONTRACTSTATUSES, 'Status'),
        'get_status', searcher='search_status')

    @classmethod
    def __setup__(cls):
        super(ContractSet, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('number_uniq', Unique(t, t.number),
                'The contract set number must be unique.')
        ]
        cls._buttons.update({
                'button_decline_set': {
                    "invisible": Bool(Equal(Eval('status'), 'declined'))},
                })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('offered.configuration')
        config = Configuration(1)
        if not config.contract_set_number_sequence:
            raise ValidationError(
                gettext('contract_set.msg_no_sequence_defined'))
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if not values.get('number'):
                values['number'] = Sequence.get_id(
                    config.contract_set_number_sequence.id)
        return super(ContractSet, cls).create(vlist)

    def get_dates(self):
        dates = []
        with Transaction().set_context(contract_set_get_dates=True):
            for contract in self.contracts:
                if contract.status == 'void':
                    continue
                dates.extend(contract.get_dates())
        return dates

    @classmethod
    @model.CoogView.button_action('contract_set.act_decline_set')
    def button_decline_set(cls, contracts):
        pass

    def get_contracts_declined(self, name):
        return all([(x.status == 'declined') for x in self.contracts])

    def get_subscribers(self, name):
        return '\n'.join(contract.subscriber.rec_name
            for contract in self.contracts)

    @classmethod
    def search_subscribers(cls, name, clause):
        return [('contracts.subscriber',) + tuple(clause[1:])]

    def get_products(self, name):
        return '\n'.join(contract.product.rec_name
            for contract in self.contracts)

    @classmethod
    def search_products(cls, name, clause):
        return [('contracts.product',) + tuple(clause[1:])]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['number']

    def get_quote_non_quote_contracts(self):
        quote, non_quote = [], []
        for contract in self.contracts:
            quote.append(contract) if contract.status == 'quote' \
                else non_quote.append(contract)
        return quote, non_quote

    def activate_set(self):
        pool = Pool()
        Event = pool.get('event')
        Warning = pool.get('res.user.warning')
        quote, non_quote = self.get_quote_non_quote_contracts()
        if non_quote:
            key = ', '.join([x.rec_name for x in non_quote])
            if Warning.check(key):
                raise UserWarning(key,
                    gettext('contract_set.msg_activate_with_non_quote',
                        contracts=key))
        for contract in quote:
            contract.activate_contract()
        Event.notify_events([self], 'activate_contract_set')

    def decline_set(self, reason):
        Contract = Pool().get('contract')
        quote, non_quote = self.get_quote_non_quote_contracts()
        if non_quote:
            key = ', '.join([x.rec_name for x in non_quote])
            if Warning.check(key):
                raise UserWarning(key,
                    gettext('contract_set.msg_decline_with_non_quote',
                        contracts=key))
        Contract.decline_contract(quote, reason)

    def get_contact(self):
        return self.contracts[0].subscriber

    def get_sender(self):
        return self.contracts[0].company.party

    @classmethod
    def get_status(cls, contract_sets, name):
        pool = Pool()
        contract = pool.get('contract').__table__()
        cursor = Transaction().connection.cursor()
        result = {x.id: None for x in contract_sets}

        cursor.execute(*contract.select(
                contract.contract_set, Max(contract.status),
                where=(contract.contract_set.in_(
                        [x.id for x in contract_sets])),
                group_by=[contract.contract_set]))

        for contract_set, status in cursor.fetchall():
            result[contract_set] = status
        return result

    @classmethod
    def search_status(cls, name, clause):
        return [('contracts.status',) + tuple(clause[1:])]

    @classmethod
    def check_contracts_unicity(cls, contracts_sets):
        for contract_set in contracts_sets:
            contract_keys = []
            for contract in contract_set.contracts:
                key = (contract.subscriber, contract.product,
                    contract.start_date)
                if key in contract_keys:
                    raise ValidationError(
                        gettext('contract_set.msg_same_contract_in_set',
                            contract=contract.rec_name,
                            contract_set=contract_set.number))
                contract_keys.append(key)

    @classmethod
    def validate(cls, contracts_sets):
        super(ContractSet, cls).validate(contracts_sets)
        cls.check_contracts_unicity(contracts_sets)


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'
    contract_set = fields.Many2One('contract.set', 'Contract Set',
        ondelete='SET NULL', states=_STATES, depends=_DEPENDS, select=True)

    def get_dates(self):
        if self.contract_set and not Transaction().context.get(
                'contract_set_get_dates', False):
            return self.contract_set.get_dates()
        return super(Contract, self).get_dates()

    def related_attachments_resources(self):
        return super(Contract, self).related_attachments_resources() + [
            str(self.contract_set)]

    @classmethod
    def validate(cls, contracts):
        pool = Pool()
        ContractSet = pool.get('contract.set')
        super(Contract, cls).validate(contracts)
        contract_sets = [contract.contract_set for contract in contracts
            if contract.contract_set]
        ContractSet.check_contracts_unicity(set(contract_sets))


class ContractSetSelectDeclineReason(model.CoogView):
    'Reason selector to decline contract set'

    __name__ = 'contract.set.decline.select_reason'

    contract_set = fields.Many2One('contract.set', 'Contract Set',
        readonly=True)
    reason = fields.Many2One('contract.sub_status', 'Reason', required=True,
        domain=[('status', '=', 'declined')])


class ContractSetDecline(model.CoogWizard):
    'Decline Contract Set Wizard'

    __name__ = 'contract.set.decline'
    start_state = 'select_reason'
    select_reason = StateView(
        'contract.set.decline.select_reason',
        'contract_set.select_set_decline_reason_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            ])
    apply = StateTransition()

    def default_select_reason(self, name):
        pool = Pool()
        ContractSet = pool.get('contract.set')
        active_id = Transaction().context.get('active_id')
        selected_contract_set = ContractSet(active_id)
        return {
            'contract_set': selected_contract_set.id,
            }

    def transition_apply(self):
        pool = Pool()
        ContractSet = pool.get('contract.set')
        reason = self.select_reason.reason
        active_id = Transaction().context.get('active_id')
        selected_contract_set = ContractSet(active_id)
        selected_contract_set.decline_set(reason)
        return 'end'


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if self.on_model and self.on_model.model == 'contract.set':
            result.append(('contract_set', 'Contract Set'))
        return result

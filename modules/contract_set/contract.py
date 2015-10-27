from sql.aggregate import Max

from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool, Equal

from trytond.modules.cog_utils import model, fields
from trytond.modules.contract import _STATES, _DEPENDS
from trytond.modules.contract.contract import CONTRACTSTATUSES
from trytond.wizard import StateTransition, StateView, Button
from trytond.modules.report_engine import Printable

__metaclass__ = PoolMeta
__all__ = [
    'ContractSet',
    'Contract',
    'ContractSetDecline',
    'ContractSetSelectDeclineReason',
    'ReportTemplate',
    'Configuration',
    ]


class Configuration:
    __name__ = 'offered.configuration'

    contract_set_number_sequence = fields.Property(
        fields.Many2One('ir.sequence', 'Contract Set Number Sequence',
            domain=[('code', '=', 'contract_set_number')]))


class ContractSet(model.CoopSQL, model.CoopView, Printable):
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
        cls._error_messages.update({
            'no_sequence_defined': 'No sequence defined in configuration '
            'for contracts set number',
            'same_contract_in_set': 'the contract %s is already defined in the'
            ' contract set %s',
            'activate_with_non_quote': ('You are activating a contract set'
                    ' with non quote contracts. The following contracts'
                    ' will not be activated : \n%s'),
            'decline_with_non_quote': ('You are declining a contract set'
                    ' with non quote contracts. The following contracts'
                    ' will not be declined : \n%s'),
            })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('offered.configuration')
        config = Configuration(1)
        if not config.contract_set_number_sequence:
            cls.raise_user_error('no_sequence_defined')
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
    @model.CoopView.button_action('contract_set.act_decline_set')
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
        quote, non_quote = self.get_quote_non_quote_contracts()
        if non_quote:
            message = ', '.join([x.rec_name for x in non_quote])
            self.raise_user_warning(message, 'activate_with_non_quote',
                message)
        for contract in quote:
            contract.activate_contract()
        Event.notify_events([self], 'activate_contract_set')

    def decline_set(self, reason):
        quote, non_quote = self.get_quote_non_quote_contracts()
        if non_quote:
            message = ', '.join([x.rec_name for x in non_quote])
            self.raise_user_warning(message, 'decline_with_non_quote',
                message)
        for contract in quote:
            contract.decline_contract(reason)

    def get_contact(self):
        return self.contracts[0].subscriber

    def get_sender(self):
        return self.contracts[0].company.party

    @classmethod
    def get_status(cls, contract_sets, name):
        pool = Pool()
        contract = pool.get('contract').__table__()
        cursor = Transaction().cursor
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
                    cls.raise_user_error('same_contract_in_set', (
                            contract.rec_name, contract_set.number))
                contract_keys.append(key)

    @classmethod
    def validate(cls, contracts_sets):
        super(ContractSet, cls).validate(contracts_sets)
        cls.check_contracts_unicity(contracts_sets)


class Contract:
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


class ContractSetSelectDeclineReason(model.CoopView):
    'Reason selector to decline contract set'

    __name__ = 'contract.set.decline.select_reason'

    contract_set = fields.Many2One('contract.set', 'Contract Set',
        readonly=True)
    reason = fields.Many2One('contract.sub_status', 'Reason', required=True,
        domain=[('status', '=', 'declined')])


class ContractSetDecline(model.CoopWizard):
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


class ReportTemplate:
    __name__ = 'report.template'

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if self.on_model and self.on_model.model == 'contract.set':
            result.append(('contract_set', 'Contract Set'))
        return result

from sql.aggregate import Max

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

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
    ]


class ContractSet(model.CoopSQL, model.CoopView, Printable):
    'Contract Set'

    __name__ = 'contract.set'
    _func_key = 'number'
    _rec_name = 'number'

    number = fields.Char('Number', required=True)
    contracts = fields.One2Many('contract', 'contract_set', 'Contracts',
        target_not_required=True)
    subscribers = fields.Function(fields.Text('Subscribers'),
        'get_subscribers', searcher='search_subscribers')
    products = fields.Function(fields.Char('Products'),
        'get_products', searcher='search_products')
    contracts_declined = fields.Function(fields.Boolean('Contracts Declined'),
        'get_contracts_declined')
    status = fields.Function(fields.Selection(CONTRACTSTATUSES, 'Status'),
        'get_status', searcher='search_status')

    @classmethod
    def __setup__(cls):
        super(ContractSet, cls).__setup__()
        cls._sql_constraints = [
            ('number_uniq', 'UNIQUE(number)',
                'The contract set number must be unique.')
        ]
        cls._buttons.update({
                'button_decline_set': {},
                })

    def get_dates(self):
        dates = []
        with Transaction().set_context(contract_set_get_dates=True):
            for contract in self.contracts:
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

    def activate_set(self):
        for contract in self.contracts:
            contract.activate_contract()
            contract.finalize_contract()

    def decline_set(self, reason):
        for contract in self.contracts:
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


class Contract:
    __name__ = 'contract'
    contract_set = fields.Many2One('contract.set', 'Contract Set',
        ondelete='SET NULL', states=_STATES, depends=_DEPENDS)

    def get_dates(self):
        if self.contract_set and not Transaction().context.get(
                'contract_set_get_dates', False):
            return self.contract_set.get_dates()
        return super(Contract, self).get_dates()


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

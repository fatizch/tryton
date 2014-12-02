from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields
from trytond.modules.contract import _STATES, _DEPENDS
from trytond.wizard import StateTransition, StateView, Button

__metaclass__ = PoolMeta
__all__ = [
    'ContractSet',
    'Contract',
    'ContractSetDecline',
    'ContractSetSelectDeclineReason',
    ]


class ContractSet(model.CoopSQL, model.CoopView):
    'Contract Set'

    __name__ = 'contract.set'
    _func_key = 'number'
    _rec_name = 'number'

    number = fields.Char('Number', required=True)
    contracts = fields.One2Many('contract', 'contract_set', 'Contracts')
    subscribers = fields.Function(fields.Char('Subscribers'),
        'get_subscribers', searcher='search_subscribers')
    products = fields.Function(fields.Char('Products'),
        'get_products', searcher='search_products')
    contracts_declined = fields.Function(fields.Boolean('Contracts Declined'),
        'get_contracts_declined')

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
            contract.save()

    def decline_set(self, reason):
        for contract in self.contracts:
            contract.decline_contract(reason)

    def generate_and_attach_reports_in_set(self, template_names):
        for contract in self.contracts:
            contract.generate_and_attach_reports(template_names)


class Contract:
    __name__ = 'contract'
    contract_set = fields.Many2One('contract.set', 'Contract Set',
        ondelete='SET NULL', states=_STATES, depends=_DEPENDS)


class ContractSetSelectDeclineReason(model.CoopSQL, model.CoopView):
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

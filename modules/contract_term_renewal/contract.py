from dateutil.relativedelta import relativedelta
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button
from trytond.pyson import Eval, And, Or
from trytond.transaction import Transaction
from trytond.modules.cog_utils import fields, model, utils

__metaclass__ = PoolMeta
__all__ = [
    'ActivationHistory',
    'Contract',
    'SelectDeclineRenewalReason',
    'DeclineRenewal',
    'Renew',
]


class ActivationHistory:
    __name__ = 'contract.activation_history'

    final_renewal = fields.Boolean('Final Renewal', readonly=True)

    @classmethod
    def default_final_renewal(cls):
        return False

    def clean_before_reactivate(self):
        super(ActivationHistory, self).clean_before_reactivate()
        self.final_renewal = False


class Contract:
    __name__ = 'contract'

    is_renewable = fields.Function(
        fields.Boolean('Is Renewable'),
        'get_is_renewable')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_decline_renewal': {
                    'invisible': And(
                        Eval('status') != 'active',
                        Eval('status') != 'quote',
                        )},
                'button_renew': {
                    'invisible': Or(
                        Eval('status') != 'active',
                        ~Eval('is_renewable'),
                        )},
                })
        cls._error_messages.update({
                'already_renewed': 'Contract %(contract_number)s has already'
                ' been renewed, with new start date at %(start_date)s . Are '
                'you sure you want to prevent renewal after %(end_date)s ?',
                })

    def get_is_renewable(self, name):
        if self.product.term_renewal_rule:
            return self.product.term_renewal_rule[0].allow_renewal
        if self.activation_history and \
                self.activation_history[-1].final_renewal:
            return False
        return False

    def get_end_date_from_given_start_date(self, start_date):
        exec_context = {'date': start_date}
        self.init_dict_for_rule_engine(exec_context)
        return self.product.get_contract_end_date(exec_context)

    def get_date_used_for_contract_end_date(self):
        date = super(Contract, self).get_date_used_for_contract_end_date()
        rule_date = self.get_end_date_from_given_start_date(
            self.start_date)
        if date and rule_date:
            return min(date, rule_date)
        elif date:
            return date
        else:
            return rule_date

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        super(Contract, cls).terminate(contracts, at_date, termination_reason)
        activation_histories = [c.activation_history[-1] for c in contracts]
        ActivationHistory.write(activation_histories, {'final_renewal': True})

    @classmethod
    def renew(cls, contracts):
        pool = Pool()
        Event = pool.get('event')
        renewed_contracts = []
        for contract in list(contracts):
            if contract.activation_history[-1].final_renewal:
                continue
            if contract.product.term_renewal_rule and not \
                    contract.product.term_renewal_rule[-1].allow_renewal:
                continue
            new_start_date = contract.end_date + relativedelta(days=1)
            if contract.activation_history[-1].start_date == new_start_date:
                continue
            contract.do_renew(new_start_date)
            renewed_contracts.append(contract)
        cls.save(renewed_contracts)
        Event.notify_events(renewed_contracts, 'renew_contract')
        return renewed_contracts

    def do_renew(self, new_start_date):
        ActivationHistory = Pool().get('contract.activation_history')
        new_act_history = ActivationHistory(contract=self,
            start_date=new_start_date)
        self.activation_history = list(self.activation_history
            ) + [new_act_history]
        new_act_history.end_date = self.get_end_date_from_given_start_date(
            new_start_date)

    @classmethod
    def decline_renewal(cls, contracts, reason):
        pool = Pool()
        Event = pool.get('event')
        Date = pool.get('ir.date')
        lang = pool.get('res.user')(Transaction().user).language
        today = utils.today()
        ActivationHistory = pool.get('contract.activation_history')
        activation_histories = [x.activation_history[-1] for x
            in contracts]
        for activation_history in activation_histories:
            if activation_history.start_date >= today:
                cls.raise_user_warning(activation_history.contract.rec_name,
                    'already_renewed', {
                        'contract_number':
                        activation_history.contract.contract_number,
                        'start_date': Date.date_as_string(
                            activation_history.start_date, lang),
                        'end_date': Date.date_as_string(
                            activation_history.end_date, lang)})
        ActivationHistory.write(activation_histories,
            {'termination_reason': reason, 'final_renewal': True})
        Event.notify_events(contracts, 'decline_contract_renewal')

    @classmethod
    @model.CoopView.button_action('contract_term_renewal.act_decline_renewal')
    def button_decline_renewal(cls, contracts):
        pass

    @classmethod
    @model.CoopView.button_action('contract_term_renewal.act_renew')
    def button_renew(cls, contracts):
        pass

    def get_report_functional_date(self, event_code):
        if event_code == 'renew_contract':
            return self.activation_history[-1].start_date
        return super(Contract, self).get_report_functional_date(event_code)


class SelectDeclineRenewalReason(model.CoopView):
    'Reason selector to decline renewal'
    __name__ = 'contract_term_renewal.decline_renewal.select_reason'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    reason = fields.Many2One('contract.sub_status', 'Reason', required=True,
        domain=[('status', '=', 'terminated')])


class DeclineRenewal(model.CoopWizard):
    'Decline Renewal Wizard'

    __name__ = 'contract_term_renewal.decline_renewal'
    start_state = 'select_reason'
    select_reason = StateView(
        'contract_term_renewal.decline_renewal.select_reason',
        'contract_term_renewal.select_decline_renewal_reason_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            ])
    apply = StateTransition()

    def default_select_reason(self, name):
        assert Transaction().context.get('active_model') == 'contract'
        active_id = Transaction().context.get('active_id')
        return {
            'contract': active_id,
            }

    def transition_apply(self):
        pool = Pool()
        Contract = pool.get('contract')
        reason = self.select_reason.reason
        selected_contract = self.select_reason.contract
        Contract.decline_renewal([selected_contract], reason)
        return 'end'


class Renew(model.CoopWizard):
    'Renewal Wizard'

    __name__ = 'contract_term_renewal.renew'
    start_state = 'renew'
    renew = StateTransition()

    def transition_renew(self):
        pool = Pool()
        Contract = pool.get('contract')
        assert Transaction().context.get('active_model') == 'contract'
        active_ids = Transaction().context.get('active_ids')
        self.renew_contracts(Contract.browse(active_ids))
        return 'end'

    @classmethod
    def renew_contracts(cls, contracts):
        pool = Pool()
        Contract = pool.get('contract')
        renewed_contracts = Contract.renew(contracts)

        keyfunc = lambda c: c.activation_history[-1].start_date
        renewed_contracts.sort(key=keyfunc)
        for new_start_date, contracts in groupby(renewed_contracts, keyfunc):
            contracts = list(contracts)
            with Transaction().set_context(
                    client_defined_date=new_start_date):
                Contract.produce_reports(contracts, 'renewal')

        return renewed_contracts

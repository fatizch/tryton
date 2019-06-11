# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button
from trytond.pyson import Eval, And, Or
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, model, utils

__all__ = [
    'ActivationHistory',
    'Contract',
    'SelectDeclineRenewalReason',
    'DeclineRenewal',
    'Renew',
    'ConfirmRenew',
    ]


class ActivationHistory(metaclass=PoolMeta):
    __name__ = 'contract.activation_history'

    final_renewal = fields.Boolean('Final Renewal', readonly=True)

    @classmethod
    def default_final_renewal(cls):
        return False

    def clean_before_reactivate(self):
        super(ActivationHistory, self).clean_before_reactivate()
        self.final_renewal = False


class Contract(metaclass=PoolMeta):
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
                'renew_impossible': 'Contract %(contract_number)s has already '
                'a planned termination. It can\'t be renewed',
                'deferment_after_renew': 'The contract %(contract)s has been '
                'renewed, the deferment will override the contract start date',
                })

    def update_start_date(self, caller=None):
        with model.error_manager():
            res = self.can_change_start_date()
        if res:
            if len(self.activation_history) > 1 and \
                    self.product.term_renewal_rule:
                self.raise_user_warning('deferment_after_renew_%s' %
                    str(self.contract_number),
                    'deferment_after_renew', {'contract': self.contract_number})
            super(Contract, self).update_start_date(caller)

    def finally_renewed(self):
        return (self.activation_history
            and self.activation_history[-1].final_renewal)

    def get_is_renewable(self, name):
        if self.finally_renewed():
            return False
        if self.product.term_renewal_rule:
            return self.product.term_renewal_rule[0].allow_renewal
        return False

    def get_end_date_from_given_start_date(self, start_date):
        exec_context = {'date': start_date}
        self.init_dict_for_rule_engine(exec_context)
        return self.product.get_contract_end_date(exec_context)

    def get_date_used_for_contract_end_date(self):
        date = super(Contract, self).get_date_used_for_contract_end_date()
        contract_start_date = self.start_date or self.initial_start_date
        rule_date = self.get_end_date_from_given_start_date(
            contract_start_date)
        if date and rule_date:
            return min(date, rule_date)
        elif date:
            return date
        else:
            return rule_date

    def _update_activation_history_start_date(self, value):
        if self.is_renewable and len(self.activation_history) > 1:
            less_act_hist = [x for x in self.activation_history
                if x.start_date <= value]
            if less_act_hist:
                to_modify = less_act_hist[-1]
                to_remove = None
                # Delete previous activation history
                if len(less_act_hist) > 1:
                    to_remove = less_act_hist[:-1]
                if to_remove:
                    self.activation_history = list(set(self.activation_history)
                        - set(to_remove))
                if to_modify.start_date != value:
                    if to_modify.end_date and to_modify.end_date < value:
                        to_modify.end_date = None
                    to_modify.start_date = value
                    self.activation_history = list(self.activation_history)
                    return
        super(Contract, self)._update_activation_history_start_date(value)

    def can_change_start_date(self):
        res = super(Contract, self).can_change_start_date()
        if not self._error_manager:
            return res
        multiple_history = self.pop_functional_error(
            'start_date_multiple_activation_history')
        if not multiple_history:
            return res
        elif multiple_history and self.product.term_renewal_rule:
            res = not self._error_manager.has_errors
        else:
            self.append_functional_error(
                'start_date_multiple_activation_history')
            res = False
        return res

    def before_activate(self):
        # We do this before super because end_date is cleared
        self.activation_history[-1].clean_before_reactivate()
        self.activation_history = list(self.activation_history)
        self.save()
        super().before_activate()

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        super(Contract, cls).terminate(contracts, at_date, termination_reason)
        activation_histories = [c.activation_history[-1] for c in contracts]
        ActivationHistory.write(activation_histories, {'final_renewal': True})

    @classmethod
    def filter_and_sort_contracts_to_renew(cls, contracts):
        res = {}

        def keyfunc(x):
            return x.activation_history[-1].end_date

        contracts = sorted(contracts, key=keyfunc)
        for end_date, contracts in groupby(contracts, key=keyfunc):
            contracts = list(contracts)
            to_renew = [x for x in contracts if x.is_renewable]
            if to_renew:
                res[end_date + relativedelta(days=1)] = to_renew
        return res

    @classmethod
    def renew(cls, contracts):
        pool = Pool()
        Event = pool.get('event')
        renewed_contracts = []
        for new_start_date, contracts_to_renew in \
                cls.filter_and_sort_contracts_to_renew(contracts).items():
            cls.before_renew(contracts_to_renew, new_start_date)
            cls.do_renew(contracts_to_renew, new_start_date)
            cls.after_renew(contracts_to_renew, new_start_date)
            Event.notify_events(contracts_to_renew, 'renew_contract')
            renewed_contracts.extend(contracts_to_renew)
        return renewed_contracts

    @classmethod
    def do_renew(cls, contracts, new_start_date):
        ActivationHistory = Pool().get('contract.activation_history')
        for contract in contracts:
            new_act_history = ActivationHistory(contract=contract,
                start_date=new_start_date,
                end_date=contract.get_end_date_from_given_start_date(
                    new_start_date))
            contract.activation_history = list(contract.activation_history
                ) + [new_act_history]
        cls.save(contracts)

    @classmethod
    def _pre_renew_methods(cls):
        return set([])

    @classmethod
    def _post_renew_methods(cls):
        return set([])

    @classmethod
    def check_contracts_renewable(cls, contracts, new_start_date):
        for contract in contracts:
            if contract.activation_history[-1].final_renewal:
                cls.append_functional_error('renew_impossible', {
                        'contract_number': contract.contract_number,
                        })

    @classmethod
    def before_renew(cls, contracts, new_start_date):
        with model.error_manager():
            cls.check_contracts_renewable(contracts, new_start_date)
        cls.execute_renewal_methods(contracts, new_start_date=new_start_date,
            kind='before')

    @classmethod
    def after_renew(cls, contracts, new_start_date):
        cls.execute_renewal_methods(contracts, new_start_date=new_start_date,
            kind='after')

    @classmethod
    def execute_renewal_methods(cls, contracts, new_start_date=None,
            kind=None):
        Method = Pool().get('ir.model.method')
        if kind == 'before':
            methods_kind = '_pre_renew_methods'
        elif kind == 'after':
            methods_kind = '_post_renew_methods'
        else:
            raise NotImplementedError
        method_names = getattr(cls, methods_kind)()
        methods = [Method.get_method('contract', x)
            for x in method_names]
        if not methods:
            return
        methods.sort(key=lambda x: x.priority)
        for method in methods:
            method.execute(None, contracts, new_start_date=new_start_date)
        cls.save(contracts)

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
    @model.CoogView.button_action('contract_term_renewal.act_decline_renewal')
    def button_decline_renewal(cls, contracts):
        pass

    @classmethod
    @model.CoogView.button_action('contract_term_renewal.act_renew')
    def button_renew(cls, contracts):
        pass

    def get_report_functional_date(self, event_code):
        if event_code == 'renew_contract':
            return self.activation_history[-1].start_date
        return super(Contract, self).get_report_functional_date(event_code)


class SelectDeclineRenewalReason(model.CoogView):
    'Reason selector to decline renewal'
    __name__ = 'contract_term_renewal.decline_renewal.select_reason'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    reason = fields.Many2One('contract.sub_status', 'Reason', required=True,
        domain=[('status', '=', 'terminated')])


class DeclineRenewal(model.CoogWizard):
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


class ConfirmRenew(model.CoogView):
    'Confirm Contract Renewal'
    __name__ = 'contract_term_renewal.renew.confirm'

    contracts = fields.One2Many('contract', None, 'Contracts', readonly=True)


class Renew(model.CoogWizard):
    'Renewal Wizard'

    __name__ = 'contract_term_renewal.renew'
    start_state = 'confirm_renew'
    confirm_renew = StateView('contract_term_renewal.renew.confirm',
        'contract_term_renewal.confirm_contract_renewal_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Confirm', 'renew', 'tryton-go-next', default=True)])
    renew = StateTransition()

    def default_confirm_renew(self, name):
        assert Transaction().context.get('active_model') == 'contract'
        return {'contracts': Transaction().context.get('active_ids')}

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
        return renewed_contracts

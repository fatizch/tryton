# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, Or, Bool

from trytond.modules.coog_core import model, fields
from trytond.modules.endorsement import relation_mixin

__metaclass__ = PoolMeta
__all__ = [
    'BillingInformation',
    'Contract',
    'Endorsement',
    'EndorsementContract',
    'EndorsementBillingInformation',
    ]


class BillingInformation(object):
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.billing_information'

    direct_debit_account_selector = fields.Function(
        fields.Many2One('bank.account', 'Bank Account', states={
                'invisible': ~Eval('search_all_direct_debit_account')},
            depends=['search_all_direct_debit_account']),
        'get_direct_debit_account_selector', 'setter_void')
    search_all_direct_debit_account = fields.Function(
        fields.Boolean('Search all direct debit accounts',
            states={'invisible': Or(~Eval('direct_debit'),
                    Bool(Eval('direct_debit_account', False)))},
            depends=['direct_debit']),
        'get_search_all_direct_debit_account', 'setter_void')

    @classmethod
    def __setup__(cls):
        super(BillingInformation, cls).__setup__()
        cls.direct_debit_account.states['invisible'] = Or(
            cls.direct_debit_account.states['invisible'],
            Eval('search_all_direct_debit_account', False))
        cls.direct_debit_account.depends += ['search_all_direct_debit_account']

    @classmethod
    def view_attributes(cls):
        return super(BillingInformation, cls).view_attributes() + \
            [('/form/group[@id="invisible"]', 'states', {'invisible': True})]

    @fields.depends('contract', 'direct_debit_account',
        'direct_debit_account_selector', 'search_all_direct_debit_account')
    def on_change_direct_debit_account_selector(self):
        if not self.direct_debit_account_selector:
            return
        if (self.contract.subscriber in
                self.direct_debit_account_selector.owners):
            self.direct_debit_account = self.direct_debit_account_selector
            self.direct_debit_account_selector = None
            self.search_all_direct_debit_account = False
            return

    def get_direct_debit_account_selector(self, name):
        return None

    def get_search_all_direct_debit_account(self, name):
        return False


class Contract:
    __name__ = 'contract'

    @classmethod
    def _future_invoices_cache_key(cls):
        return super(Contract, cls)._future_invoices_cache_key() + (
            Transaction().context.get('will_be_rollbacked', False),)

    def rebill_endorsement_dates(self):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        return sorted([datetime.datetime.combine(
                    endorsement.effective_date, datetime.time()) or
            endorsement.application_date
            for endorsement in Endorsement.search([
                    ('contracts', '=', self.id),
                    ('state', '=', 'applied')])
            if endorsement.definition.requires_rebill()])

    def _get_invoice_rrule_and_billing_information(self, start):
        pool = Pool()
        Configuration = pool.get('offered.configuration')
        config = Configuration(1)
        invoice_rrule = super(Contract,
            self)._get_invoice_rrule_and_billing_information(start)
        if not config.split_invoices_on_endorsement_dates:
            return invoice_rrule
        endorsement_dates = self.rebill_endorsement_dates()
        if endorsement_dates:
            invoice_rrule[0].rrule(endorsement_dates)
        return invoice_rrule

    @classmethod
    def recalculate_premium_after_endorsement(cls, contracts, caller=None):
        if Transaction().context.get('endorsement_soft_apply', False):
            return
        if not isinstance(caller, (tuple, list)):
            caller = [caller]
        if caller[0].__name__ != 'endorsement.contract':
            return
        for endorsement in caller:
            definition = endorsement.endorsement.definition
            if endorsement.contract not in contracts:
                continue
            premium_start = definition.get_premium_computation_start(
                endorsement)
            endorsement.contract.calculate_prices([endorsement.contract],
                start=premium_start)

    @classmethod
    def rebill_after_endorsement(cls, contracts, caller=None):
        if Transaction().context.get('will_be_rollbacked', False):
            return
        if not isinstance(caller, (tuple, list)):
            caller = [caller]
        if caller[0].__name__ != 'endorsement.contract':
            return
        for endorsement in caller:
            definition = endorsement.endorsement.definition
            if endorsement.contract not in contracts:
                continue
            premium_start = definition.get_premium_computation_start(
                endorsement)
            rebill_end = definition.get_rebill_end(endorsement)
            rebill_post_end = definition.get_rebill_post_end(endorsement)
            endorsement.contract.rebill(start=premium_start, end=rebill_end,
                post_end=rebill_post_end)

    @classmethod
    def reconcile_after_endorsement(cls, contracts, caller=None):
        if Transaction().context.get('will_be_rollbacked', False):
            return
        if not isinstance(caller, (tuple, list)):
            caller = [caller]
        if caller[0].__name__ != 'endorsement.contract':
            return
        Pool().get('contract').reconcile([x.contract for x in caller])


class Endorsement:
    __name__ = 'endorsement'

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind == 'billing_information':
            return Pool().get('endorsement.contract')(endorsement=self)
        return super(Endorsement, self).new_endorsement(endorsement_part)

    def find_parts(self, endorsement_part):
        if endorsement_part.kind in 'billing_information':
            return self.contract_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)


class EndorsementContract:
    __name__ = 'endorsement.contract'

    billing_informations = fields.One2Many(
        'endorsement.contract.billing_information',
        'contract_endorsement', 'Billing Informations', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'], delete_missing=True,
        context={'definition': Eval('definition')})

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._error_messages.update({
                'mes_billing_modifications': 'Billing Modifications',
                })

    def get_endorsement_summary(self, name):
        result = super(EndorsementContract, self).get_endorsement_summary(name)
        previous_billing_information = self.base_instance.billing_information
        billing_summary = [billing_information.get_diff(
                'contract.billing_information', previous_billing_information)
            for billing_information in self.billing_informations]
        if billing_summary:
            result[1].append(['%s :' % self.raise_user_error(
                   'mes_billing_modifications', raise_exception=False),
                billing_summary])
        return result

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        contract_idx = order.index('contract')
        order.insert(contract_idx + 1, 'contract.billing_information')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.billing_information'] += \
                contract.billing_informations
        new_premiums = []
        for option in instances['contract.option']:
            if option.covered_element:
                new_premiums += option.premiums
        for covered_element in instances['contract.covered_element']:
            new_premiums += covered_element.premiums
        for extra_premium in instances['contract.option.extra_premium']:
            new_premiums += extra_premium.premiums
        instances['contract.premium'] += new_premiums

    def apply_values(self):
        values = super(EndorsementContract, self).apply_values()
        billing_informations = []
        for billing_information in self.billing_informations:
            billing_informations.append(billing_information.apply_values())
        if billing_informations:
            values['billing_informations'] = billing_informations
        return values


class EndorsementBillingInformation(relation_mixin(
            'endorsement.contract.billing_information.field',
            'billing_information', 'contract.billing_information',
            'Billing Informations'),
        model.CoogSQL, model.CoogView):
    'Endorsement Billing Information'

    __name__ = 'endorsement.contract.billing_information'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementBillingInformation, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    @classmethod
    def _ignore_fields_for_matching(cls):
        return super(EndorsementBillingInformation,
            cls)._ignore_fields_for_matching() | {'contract'}

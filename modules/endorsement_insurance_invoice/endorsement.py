import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import relation_mixin

__metaclass__ = PoolMeta
__all__ = [
    'BillingInformation',
    'ContractInvoice',
    'CommissionInvoice',
    'Contract',
    'Endorsement',
    'EndorsementContract',
    'EndorsementBillingInformation',
    ]


class BillingInformation(object):
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.billing_information'


class ContractInvoice:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.invoice'


class CommissionInvoice:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.invoice.commission'


class Contract:
    __name__ = 'contract'

    def get_rebill_end_date(self, start_date=None):
        Date = Pool().get('ir.date')
        if not start_date:
            start_date = Date.today()
        if not self.last_invoice_end or start_date > self.last_invoice_end:
            # Nothing to rebill, the contract was not billed at the required
            # start_date
            return None
        # It is possible that the end_date changed since the last billing so
        # the last_invoice_end may be too far in the future
        return min(self.end_date or datetime.date.max, self.last_invoice_end)

    def rebill(self, at_date=None):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')

        # Recalculate prices
        self.calculate_prices([self], at_date)

        # Store the end date of the last invoice to be able to know up til when
        # we should rebill
        rebill_end = self.get_rebill_end_date(at_date)

        invoices_to_delete = ContractInvoice.search([
                ('contract', '=', self.id),
                ('end', '>=', at_date),
                ('invoice_state', '!=', 'cancel')],
            order=[('start', 'ASC')])

        # We want to post the invoices until the last current invoice post date
        post_date = datetime.date.min
        for invoice in invoices_to_delete:
            if invoice.invoice_state != 'posted':
                break
            post_date = invoice.start
        ContractInvoice.delete(invoices_to_delete)

        # Rebill
        self.invoice([self], rebill_end)

        # Post
        if post_date < at_date:
            return
        invoices_to_post = Invoice.search([
                ('contract', '=', self.id),
                ('start', '<=', post_date),
                ('state', '=', 'validated')])
        if invoices_to_post:
            Invoice.post(invoices_to_post)


class Endorsement:
    __name__ = 'endorsement'

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind == 'billing_information':
            return Pool().get('endorsement.contract')(endorsement=self)
        return super(Endorsement, self).new_endorsement(endorsement_part)

    @classmethod
    def apply(cls, endorsement_groups):
        super(Endorsement, cls).apply(endorsement_groups)
        to_rebill = [x for x in endorsement_groups
            if x.definition.requires_contract_rebill]
        if not to_rebill:
            return
        cls.rebill_contracts(to_rebill)

    @classmethod
    def draft(cls, endorsement_groups):
        super(Endorsement, cls).draft(endorsement_groups)
        to_rebill = [x for x in endorsement_groups
            if x.definition.requires_contract_rebill]
        if not to_rebill:
            return
        cls.rebill_contracts(to_rebill)

    @classmethod
    def rebill_contracts(cls, endorsements):
        to_rebill = {}
        for endorsement in endorsements:
            for contract in endorsement.contracts:
                if contract not in to_rebill:
                    to_rebill[contract] = endorsement.effective_date
                else:
                    to_rebill[contract] = min(to_rebill[contract],
                        endorsement.effective_date)
        for contract, at_date in to_rebill.iteritems():
            contract.rebill(at_date)


class EndorsementContract:
    __name__ = 'endorsement.contract'

    billing_informations = fields.One2Many(
        'endorsement.contract.billing_information',
        'contract_endorsement', 'Billing Informations', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'],
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
        billing_summary = '\n'.join([billing_information.get_summary(
                    'contract.billing_information',
                    previous_billing_information, indent=4)
                for billing_information in self.billing_informations])
        if billing_summary:
            result += '  %s :\n' % self.raise_user_error(
                'mes_billing_modifications', raise_exception=False)
            result += billing_summary
            result += '\n\n'
        return result

    def _restore_history(self):
        contract, hcontract = super(EndorsementContract,
            self)._restore_history()
        billing_info_ids = set((billing_info.id for billing_info in (
                    contract.billing_informations +
                    hcontract.billing_informations)))
        Pool().get('contract.billing_information').restore_history(list(
                billing_info_ids), self.applied_on)
        return contract, hcontract

    @property
    def apply_values(self):
        values = super(EndorsementContract, self).apply_values
        billing_informations = []
        for billing_information in self.billing_informations:
            billing_informations.append(billing_information.apply_values)
        if billing_informations:
            values['billing_informations'] = billing_informations
        return values

    def set_applied_on(self, datetime):
        super(EndorsementContract, self).set_applied_on(datetime)
        for billing_information in self.billing_informations:
            billing_information.applied_on = datetime
        self.billing_informations = list(self.billing_informations)


class EndorsementBillingInformation(relation_mixin(
            'endorsement.contract.billing_information.field',
            'billing_information', 'contract.billing_information',
            'Billing Informations'),
        model.CoopSQL, model.CoopView):
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

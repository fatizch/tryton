import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
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


class Contract:
    __name__ = 'contract'

    def get_rebill_end_date(self, start_date):
        return min(self.end_date or datetime.date.max,
            self.last_invoice_end or start_date)

    def get_rebill_post_end(self, start_date):
        ContractInvoice = Pool().get('contract.invoice')
        last_posted = ContractInvoice.search([
                ('contract', '=', self.id),
                ('end', '>=', start_date),
                ('invoice_state', 'not in', ('cancel', 'draft', 'validated')),
                ], order=[('start', 'DESC')], limit=1)
        return last_posted[0].start if last_posted else datetime.date.min

    def rebill(self, at_date):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        # Recalculate prices
        self.calculate_prices([self], at_date)

        # Store the end date of the last invoice to be able to know up til when
        # we should rebill
        rebill_end = self.get_rebill_end_date(at_date)

        # Calculate the date until which we will repost invoices
        post_end = self.get_rebill_post_end(at_date)

        # Delete or cancel overlapping invoices
        self.clean_up_contract_invoices([self], from_date=at_date)

        # Rebill
        if rebill_end:
            self.invoice([self], rebill_end)

        # Post
        if post_end < at_date:
            return
        invoices_to_post = Invoice.search([
                ('contract', '=', self.id),
                ('start', '<=', post_end),
                ('state', '=', 'validated')])
        if invoices_to_post:
            Invoice.post(invoices_to_post)

    def _get_invoice_rrule_and_billing_information(self, start):
        invoice_rrule = super(Contract,
            self)._get_invoice_rrule_and_billing_information(start)
        Endorsement = Pool().get('endorsement')
        [invoice_rrule[0].rdate(
                datetime.datetime.fromordinal(
                    endorsement.effective_date.toordinal()) or
                endorsement.application_date.date())
            for endorsement in Endorsement.search([
                        ('contracts', '=', self.id),
                        ('state', '=', 'applied')])
            if endorsement.definition.requires_contract_rebill]
        return invoice_rrule


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

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.billing_information'] += \
                contract.billing_informations
        for obj in (instances['contract'] +
                instances['contract.covered_element'] +
                instances['contract.option']):
            instances['contract.premium'] += obj.premiums

    def apply_values(self):
        values = super(EndorsementContract, self).apply_values()
        billing_informations = []
        for billing_information in self.billing_informations:
            billing_informations.append(billing_information.apply_values())
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

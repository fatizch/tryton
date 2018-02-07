# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model, coog_date
from trytond.modules.endorsement.endorsement import field_mixin


__all__ = [
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementBillingInformationField',
    'Product',
    ]


class EndorsementDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.definition'

    def requires_rebill(self):
        return 'recalculate_premium_after_endorsement' in \
            self.get_methods_for_model('contract')

    def get_premium_computation_start(self, contract_endorsement):
        contract = contract_endorsement.contract
        effective_date = contract_endorsement.endorsement.effective_date

        if (not contract.start_date or
                effective_date == contract.initial_start_date):
            # Recalculate whole contract (datetime.date.min rather than
            # contract.start_date to manage start date modification)
            return datetime.date.min

        # Redmine #6192
        # From a business point of view, the contract ends the day after
        # termination endorsement's effective date
        for part in self.endorsement_parts:
            if part.code == 'stop_contract':
                return coog_date.add_day(effective_date, 1)

        pool = Pool()
        config = pool.get('offered.configuration')(1)
        if not config.split_invoices_on_endorsement_dates:
            return effective_date

        # Special case : We must recompute one day before the effective date,
        # unless the effective date is synced with a billing date
        periods = contract.get_invoice_periods(
            coog_date.add_day(effective_date, 1),
            coog_date.add_day(effective_date, -1))
        if effective_date in [x[0] for x in periods]:
            # There was a planned billing anyway
            return effective_date
        return coog_date.add_day(effective_date, -1)

    def get_rebill_end(self, contract_endorsement):
        if contract_endorsement.contract.status == 'void':
            return None
        return contract_endorsement.contract.activation_history[-1].end_date \
            or max(contract_endorsement.contract.last_invoice_end or
            datetime.date.min, contract_endorsement.endorsement.effective_date)

    def get_rebill_post_end(self, contract_endorsement):
        ContractInvoice = Pool().get('contract.invoice')
        last_posted = ContractInvoice.search([
                ('contract', '=', contract_endorsement.contract.id),
                ('end', '>=', contract_endorsement.endorsement.effective_date),
                ('invoice_state', 'not in', ('cancel', 'draft', 'validated')),
                ], order=[('start', 'DESC')], limit=1)
        if not last_posted:
            return None
        if (last_posted[0].start <
                contract_endorsement.endorsement.effective_date <=
                last_posted[0].end):
            return contract_endorsement.endorsement.effective_date
        return last_posted[0].start


class EndorsementPart:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.part'

    billing_information_fields = fields.One2Many(
        'endorsement.contract.billing_information.field', 'endorsement_part',
        'Billing Information Fields', states={
            'invisible': Eval('kind', '') != 'billing_information'},
        depends=['kind'], delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(
            ('billing_information', 'Billing Information'))

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        super(EndorsementPart, cls).__register__(module)
        # Migration from 1.4 : remove requires_contract_rebill
        part_h = TableHandler(cls, module)
        if part_h.column_exist('requires_contract_rebill'):
            part_h.drop_column('requires_contract_rebill')

    @fields.depends('kind')
    def on_change_with_endorsed_model(self, name=None):
        if self.kind == 'billing_information':
            return Pool().get('ir.model').search([
                    ('model', '=', 'contract')])[0].id
        return super(EndorsementPart, self).on_change_with_endorsed_model(name)

    def clean_up(self, endorsement):
        super(EndorsementPart, self).clean_up(endorsement)
        if self.billing_information_fields:
            self.clean_up_relation(endorsement, 'billing_information_fields',
                'billing_informations')


class EndorsementBillingInformationField(
        field_mixin('contract.billing_information'), model.CoogSQL,
        model.CoogView):
    'Endorsement Billing Information Field'

    __name__ = 'endorsement.contract.billing_information.field'


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    def get_contract_dates(self, dates, contract):
        super(Product, self).get_contract_dates(dates, contract)
        dates |= set([x.date() for x in contract.rebill_endorsement_dates()])

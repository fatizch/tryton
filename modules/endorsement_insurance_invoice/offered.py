import datetime

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementBillingInformationField',
    ]


class EndorsementDefinition:
    __name__ = 'endorsement.definition'

    def requires_rebill(self):
        return 'recalculate_premium_after_endorsement' in \
            self.get_methods_for_model('contract')

    def get_premium_computation_start(self, contract_endorsement):
        if (contract_endorsement.endorsement.effective_date ==
                contract_endorsement.contract.start_date):
            # Recalcul whole contract (datetime.date.min rather than
            # contract.start_date to manage start date modification)
            return datetime.date.min
        return contract_endorsement.endorsement.effective_date

    def get_rebill_end(self, contract_endorsement):
        return contract_endorsement.contract.end_date or max(
            contract_endorsement.contract.last_invoice_end or
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
        cursor = Transaction().cursor
        TableHandler = backend.get('TableHandler')
        super(EndorsementPart, cls).__register__(module)
        # Migration from 1.4 : remove requires_contract_rebill
        part_h = TableHandler(cursor, cls, module)
        if part_h.column_exist('requires_contract_rebill'):
            part_h.drop_column('requires_contract_rebill')

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
        field_mixin('contract.billing_information'), model.CoopSQL,
        model.CoopView):
    'Endorsement Billing Information Field'

    __name__ = 'endorsement.contract.billing_information.field'

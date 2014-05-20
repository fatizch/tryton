from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval, And
from trytond.transaction import Transaction

from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Sepa Mandate', states={
            'invisible': ~Eval('direct_debit'),
            'required': And(Eval('direct_debit', False),
                (Eval('status') == 'active'))},
        domain=[('party', '=', Eval('subscriber')),
            ('company', '=', Eval('company')),
            ('account_number.account', '=', Eval('direct_debit_account'))],
        depends=['subscriber', 'company', 'direct_debit']
        )

    def init_SEPA_mandate(self):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        Sequence = pool.get('ir.sequence')
        if (self.direct_debit and self.direct_debit_account
                and len(self.direct_debit_account.numbers) > 0
                and self.sepa_mandate is None):
            journal = Journal.search([
                ('company', '=', self.company.id),
                ('currency', '=', self.currency),
                ('process_method', '=', 'sepa')])[0]
            if journal and journal.umr_sequence:
                with Transaction().set_context(date=utils.today()):
                    umr_identification = Sequence.get_id(
                        journal.umr_sequence.id)
            else:
                umr_identification = None

            Mandate = Pool().get('account.payment.sepa.mandate')
            mandate, = Mandate.create([{
                'party': self.subscriber.id,
                'account_number': self.direct_debit_account.numbers[0],
                'company': self.company,
                'type': 'recurrent',
                'state': 'draft',
                'identification': umr_identification,
                }])
            self.sepa_mandate = mandate

    def before_activate(self, contract_dict=None):
        super(Contract, self).before_activate()
        #TODO search mandate only if necessary
        if self.subscriber.sepa_mandates or not self.subscriber.bank_accounts:
            return
        Mandate = Pool().get('account.payment.sepa.mandate')
        mandate = Mandate()
        mandate.party = self.subscriber
        mandate.account_number = self.subscriber.bank_accounts[0].numbers[0]
        #TODO manage identification with sequence
        #mandate.identification =
        mandate.type = 'recurrent'
        mandate.signature_date = contract_dict['start_date']
        mandate.state = 'validated'
        mandate.save()

    @fields.depends('direct_debit_account')
    def on_change_direct_debit_account(self):
        if (self.direct_debit_account
                and len(self.direct_debit_account.numbers) > 0
                and self.direct_debit_account.numbers[0].mandates
                and len(self.direct_debit_account.numbers[0].mandates) > 0):
            return {'sepa_mandate':
                self.direct_debit_account.numbers[0].mandates[0].id}
        else:
            return {}

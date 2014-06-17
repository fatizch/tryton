from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval, And
from trytond.transaction import Transaction
from trytond import backend

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractBillingInformation',
    ]


class Contract:
    __name__ = 'contract'

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


class ContractBillingInformation:
    __name__ = 'contract.billing_information'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Sepa Mandate', states={
            'invisible': ~Eval('direct_debit'),
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active'))},
        domain=[
            ('account_number.account', '=', Eval('direct_debit_account')),
            ('party', '=',
                Eval('_parent_contract', {}).get('subscriber'))],
        depends=['direct_debit', 'direct_debit_account']
        )

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        the_table = TableHandler(cursor, cls, module_name)
        Contract = pool.get('contract')
        contract_table = TableHandler(cursor, Contract, module_name)
        if (not the_table.column_exist('sepa_mandate') and
                contract_table.column_exist('sepa_mandate')):
            migrate = True

        super(ContractBillingInformation, cls).__register__(module_name)

        # Migration from 1.1: Billing change
        if migrate:
            cursor.execute("update contract_billing_information "
                "set sepa_mandate = c.sepa_mandate "
                "from contract_billing_information as b, "
                "contract as c where b.contract = c.id")

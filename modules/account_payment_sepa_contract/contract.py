from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, And
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractBillingInformation',
    'ChangeBankAccount',
    'ChangeBankAccountSelect',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.billing_informations.domain.append(
            ['OR',
                ('sepa_mandate', '=', None),
                ('sepa_mandate.party', '=', Eval('subscriber'))])
        cls.billing_informations.depends.append('subscriber')

    def init_sepa_mandate(self):
        self.billing_information.init_sepa_mandate()

    def before_activate(self, contract_dict=None):
        super(Contract, self).before_activate()
        self.init_sepa_mandate()

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            contract.init_sepa_mandate()


class ContractBillingInformation:
    __name__ = 'contract.billing_information'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Sepa Mandate', states={
            'invisible': ~Eval('direct_debit'),
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active'))},
        domain=[
            ('account_number.account', '=', Eval('direct_debit_account'))],
        depends=['direct_debit', 'direct_debit_account'], ondelete='RESTRICT',
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

    @classmethod
    def _export_light(cls):
        return (super(ContractBillingInformation, cls)._export_light() |
            set(['sepa_mandate']))

    def init_sepa_mandate(self):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        if (not self.direct_debit or self.sepa_mandate or
                not self.direct_debit_account):
            return
        numbers_id = [number.id
            for number in self.direct_debit_account.numbers]
        mandates = Mandate.search([
                ('type', '=', 'recurrent'),
                ('scheme', '=', 'CORE'),
                ('account_number', 'in', numbers_id),
                ('party', '=', self.contract.subscriber.id),
                ])
        for mandate in mandates:
            self.sepa_mandate = mandate
            self.save()
            return
        mandate = Mandate(
            party=self.contract.subscriber,
            account_number=self.direct_debit_account.numbers[0],
            type='recurrent',
            scheme='CORE',
            signature_date=(self.contract.signature_date or
                self.contract.start_date),
            company=self.contract.company,
            state='validated')
        self.sepa_mandate = mandate
        self.save()

    @classmethod
    def copy(cls, instances, default=None):
        default = {} if default is None else default.copy()
        if Transaction().context.get('copy_mode', '') == 'functional':
            skips = cls._export_skips() | cls.functional_skips_for_duplicate()
            for x in skips:
                default.setdefault(x, None)
        return super(ContractBillingInformation, cls).copy(instances,
            default=default)

    @classmethod
    def functional_skips_for_duplicate(cls):
        return set(['sepa_mandate'])


class ChangeBankAccount:
    __name__ = 'contract.bank_account.change'

    def update_contract(self):
        super(ChangeBankAccount, self).update_contract()
        pool = Pool()
        data = self.select_new_account
        if not data.need_new_sepa_mandate:
            new_mandate = data.new_sepa_mandate
        else:
            SepaMandate = pool.get('account.payment.sepa.mandate')
            new_mandate = SepaMandate()
            new_mandate.party = data.subscriber
            new_mandate.account_number = data.new_bank_account.numbers[0]
            new_mandate.type = 'recurrent'
            new_mandate.scheme = 'CORE'
            new_mandate.signature_date = data.sepa_mandate_date
            new_mandate.state = 'validated'
            new_mandate.company = data.contract.company
            new_mandate.save()
        for contract in list(data.other_contracts) + [data.contract]:
            contract.billing_informations[-1].sepa_mandate = new_mandate


class ChangeBankAccountSelect:
    __name__ = 'contract.bank_account.change.select'

    sepa_mandate_date = fields.Date('Sepa Mandate Signature Date',
        states={
            'required': Eval('need_new_sepa_mandate', False),
            'invisible': ~Eval('need_new_sepa_mandate', False)},
        domain=[('sepa_mandate_date', '<=', Eval('max_signature_date'))],
        depends=['need_new_sepa_mandate', 'max_signature_date'])
    need_new_sepa_mandate = fields.Boolean('Need new Sepa Mandate',
        states={'invisible': True})
    max_signature_date = fields.Date('Max Signature Date',
        states={'invisible': True})
    new_sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'New Sepa Mandate', states={'invisible': True})

    @fields.depends('effective_date', 'max_signature_date',
        'need_new_sepa_mandate', 'new_bank_account', 'new_sepa_mandate',
        'other_contracts', 'possible_contracts', 'subscriber')
    def on_change_new_bank_account(self):
        self.max_signature_date = min(utils.today(), self.effective_date)
        if not self.new_bank_account:
            self.need_new_sepa_mandate = False
            self.new_sepa_mandate = None
            return
        self.need_new_sepa_mandate = True
        for elem in sum([list(number.mandates)
                    for number in self.new_bank_account.numbers], []):
            if self.subscriber == elem.party:
                self.need_new_sepa_mandate = False
                self.new_sepa_mandate = elem
                break
        else:
            self.new_sepa_mandate = None
        if not self.need_new_sepa_mandate:
            if set(self.other_contracts) != set(self.possible_contracts):
                self.need_new_sepa_mandate = True

    @fields.depends('need_new_sepa_mandate', 'new_sepa_mandate',
        'other_contracts', 'possible_contracts')
    def on_change_other_contracts(self):
        if set(self.other_contracts) == set(self.possible_contracts):
            self.need_new_sepa_mandate = False
        elif not self.new_sepa_mandate:
            self.need_new_sepa_mandate = True

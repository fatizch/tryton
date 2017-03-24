# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, And
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.coog_core import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractBillingInformation',
    ]


class Contract:
    __name__ = 'contract'

    def init_sepa_mandate(self):
        # Force refresh of link as contract version could be outdated
        self.billing_information.contract = self
        self.billing_information.init_sepa_mandate()

    def after_activate(self):
        super(Contract, self).after_activate()
        self.init_sepa_mandate()

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            contract.init_sepa_mandate()

    @classmethod
    def update_mandates_from_date(cls, contracts, date):
        # Update sepa mandate on already generated invoices from a given start
        # date. The basic idea is to modify existing validated or posted
        # invoices for which there is a planned payment after the date.
        Invoice = Pool().get('account.invoice')
        update_data = {contract.id: utils.get_value_at_date(
                contract.billing_informations, date).sepa_mandate
            for contract in contracts}
        clause = ['OR'] + [
            [('contract', '=', contract), ('state', '=', 'posted'),
                ('party', '=', mandate.party)]
            for contract, mandate in update_data.items()]

        invoices = Invoice.search(clause)
        to_save = []
        for invoice in invoices:
            if not invoice.sepa_mandate:
                continue
            if invoice.state == 'posted' and max(
                    [x.payment_date or x.maturity_date for x in
                        invoice.lines_to_pay] or [datetime.date.min]) < date:
                continue
            invoice.sepa_mandate = update_data[invoice.contract.id]
            to_save.append(invoice)
        if to_save:
            Invoice.save(to_save)

    def action_required_when_payments_failed(self):
        # when contract is void without due amount no need to process any
        # action following a payment failed
        return self.status != 'void' or self.balance > 0


class ContractBillingInformation:
    __name__ = 'contract.billing_information'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate',
        'Sepa Mandate', states={
            'invisible': ~Eval('direct_debit'),
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active')),
            'readonly': Eval('contract_status') != 'quote',
            }, domain=[
            ('account_number.account', '=', Eval('direct_debit_account'))],
        depends=['direct_debit', 'direct_debit_account', 'contract_status'],
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        the_table = TableHandler(cls, module_name)
        Contract = pool.get('contract')
        contract_table = TableHandler(Contract, module_name)
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
    def _migrate_payer(cls):
        # Migrate from 1.8: Add payer
        # override behavior defined in contract_insurance_invoice
        # module to migrate payer from SEPA mandate
        pool = Pool()
        cursor = Transaction().connection.cursor()
        Mandate = pool.get('account.payment.sepa.mandate')
        sepa_mandate = Mandate.__table__()
        contract_billing = pool.get('contract.billing_information').__table__()

        update_data = contract_billing.join(sepa_mandate, condition=(
                contract_billing.sepa_mandate == sepa_mandate.id)
            ).select(contract_billing.id.as_('billing_info'),
                sepa_mandate.party)

        cursor.execute(*contract_billing.update(
                columns=[contract_billing.payer],
                values=[update_data.party],
                from_=[update_data],
                where=(contract_billing.id == update_data.billing_info)))

    @classmethod
    def _export_light(cls):
        return (super(ContractBillingInformation, cls)._export_light() |
            set(['sepa_mandate']))

    def new_mandate(self, type_, scheme, state):
        Mandate = Pool().get('account.payment.sepa.mandate')
        return Mandate(
            party=self.contract.payer,
            account_number=self.direct_debit_account.numbers[0],
            type=type_,
            scheme=scheme,
            signature_date=(self.contract.signature_date or
                self.contract.start_date),
            company=self.contract.company,
            state=state)

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
                ('party', '=', self.contract.payer.id),
                ])
        for mandate in mandates:
            self.sepa_mandate = mandate
            self.save()
            return
        self.sepa_mandate = self.new_mandate('recurrent', 'CORE', 'validated')
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

    @fields.depends('direct_debit_account', 'sepa_mandate')
    def on_change_billing_mode(self):
        previous_account = self.direct_debit_account
        super(ContractBillingInformation, self).on_change_billing_mode()
        if previous_account != self.direct_debit_account:
            self.sepa_mandate = None

    @fields.depends('direct_debit_account', 'sepa_mandate')
    def on_change_direct_debit_account(self):
        if not self.direct_debit_account:
            self.sepa_mandate = None

    @fields.depends('contract', 'payer', 'sepa_mandate', 'date',
        'direct_debit_account')
    def on_change_payer(self):
        Mandate = Pool().get('account.payment.sepa.mandate')
        super(ContractBillingInformation, self).on_change_payer()
        self.sepa_mandate = None
        if self.direct_debit_account and self.payer and self.contract \
                and self.direct_debit_account:
            possible_mandates = Mandate.search([
                    ('party', '=', self.payer.id),
                    ('account_number.account', '=',
                        self.direct_debit_account.id),
                    ('signature_date', '>=', self.date
                        or self.contract.start_date)
                    ])
            if possible_mandates:
                self.sepa_mandate = possible_mandates[0]

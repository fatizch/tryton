# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, And, If, Bool
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractBillingInformation',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.billing_informations.domain.append(
            ['OR',
                ('sepa_mandate', '=', None),
                ('sepa_mandate.party', '=', Eval('subscriber')),
                If(Bool(Eval('id', False)),
                    [('id', 'not in', Eval('valid_billing_informations'))],
                    [])
            ])
        cls.billing_informations.depends.extend(['subscriber',
                'valid_billing_informations'])

    @fields.depends('subscriber', 'billing_informations')
    def on_change_subscriber(self):
        Mandate = Pool().get('account.payment.sepa.mandate')
        super(Contract, self).on_change_subscriber()
        if not self.billing_informations:
            return
        new_billing_information = self.billing_informations[-1]
        if new_billing_information.direct_debit_account is None:
            new_billing_information.sepa_mandate = None
        else:
            possible_mandates = Mandate.search([
                    ('party', '=', self.subscriber.id),
                    ('account_number.account', '=',
                        new_billing_information.direct_debit_account.id)
                    ])
            if possible_mandates:
                new_billing_information.sepa_mandate = possible_mandates[0]
            else:
                new_billing_information.sepa_mandate = None
        self.billing_informations = [new_billing_information]

    def init_sepa_mandate(self):
        self.billing_information.init_sepa_mandate()

    def before_activate(self):
        super(Contract, self).before_activate()
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
            [('contract', '=', contract), ('state', '=', 'posted')]
            for contract in update_data.keys()]

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

    @fields.depends('direct_debit_account', 'sepa_mandate')
    def on_change_billing_mode(self):
        previous_account = self.direct_debit_account
        super(ContractBillingInformation, self).on_change_billing_mode()
        if previous_account != self.direct_debit_account:
            self.sepa_mandate = None

    @fields.depends('direct_debit_account')
    def on_change_direct_debit_account(self):
        if not self.direct_debit_account:
            self.sepa_mandate = None

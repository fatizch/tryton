from collections import defaultdict
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Dunning',
    'Level',
    ]


class Dunning:
    __name__ = 'account.dunning'

    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_line_field', searcher='search_line_field')

    @classmethod
    def _overdue_line_domain(cls, date):
        domain = super(Dunning, cls)._overdue_line_domain(date)
        domain.extend([
                ('payment_amount', '>', 0),
                ('contract', '!=', None)
                ])
        return domain

    @classmethod
    def process_dunning_per_level(cls, dunnings):
        '''
            This method will filter to treat only the higher level for a
            contract
        '''
        contracts = {}
        for dunning in dunnings:
            if dunning.contract not in contracts:
                contracts[dunning.contract] = dunning
            elif (contracts[dunning.contract].level.sequence <
                    dunning.level.sequence):
                contracts[dunning.contract] = dunning
        super(Dunning, cls).process_dunning_per_level(contracts.values())

    def get_reference_object_for_edm(self, template):
        if not self.contract:
            return super(Dunning, self).get_reference_object_for_edm(template)
        return self.contract


class Level:
    __name__ = 'account.dunning.level'

    contract_action = fields.Selection([
            ('', ''),
            ('terminate', 'Terminate Contract'),
            ('hold_invoicing', 'Hold Invoicing'),
            ('hold', 'Hold Contract')], 'Contract Action')
    termination_mode = fields.Selection([
            ('at_last_posted_invoice', 'At Last Posted Invoice'),
            ('at_last_paid_invoice', 'At Last Paid Invoice')],
            'Termination Mode', depends=['contract_action'],
            states={'invisible': Eval('contract_action') != 'terminate'})
    skip_level_for_payment = fields.Boolean('Skip Level For Payment',
        help='Skip level if line is paid by payment')
    dunning_fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        domain=[('type', '=', 'fixed')],
        help="A fee invoice will be created. Only for dunnings on contracts.")

    def process_hold_contracts(self, dunnings):
        pool = Pool()
        Contract = pool.get('contract')
        SubStatus = pool.get('contract.sub_status')
        hold_reason, = SubStatus.search([
                ('code', '=', 'unpaid_premium_hold')])
        contracts = set()
        for dunning in dunnings:
            if not dunning.contract:
                continue
            contracts.add(dunning.contract)
        if not contracts:
            return
        Contract.hold(list(contracts), hold_reason)

    def process_terminate_contracts(self, dunnings):
        pool = Pool()
        Contract = pool.get('contract')
        SubStatus = pool.get('contract.sub_status')
        to_terminate = defaultdict(list)
        termination_reason, = SubStatus.search([
                ('code', '=', 'unpaid_premium_termination')])
        for dunning in dunnings:
            if not dunning.contract:
                continue
            if self.termination_mode == 'at_last_posted_invoice':
                date = dunning.contract.last_posted_invoice_end
            elif self.termination_mode == 'at_last_paid_invoice':
                date = dunning.contract.last_paid_invoice_end or \
                    dunning.contract.last_posted_invoice_end
            if (dunning.contract.termination_reason == termination_reason and
                    dunning.contract.end_date == date):
                continue
            to_terminate[date].append(dunning.contract)
        for date, contracts in to_terminate.iteritems():
            Contract.terminate(contracts, date, termination_reason)

    def get_fee_invoice_lines(self, fee, contract):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        return [InvoiceLine(
                type='line',
                description=fee.name,
                origin=contract,
                quantity=1,
                unit=None,
                unit_price=contract.currency.round(fee.amount),
                taxes=0,
                invoice_type='out_invoice',
                account=fee.product.account_revenue_used,
                )]

    def get_fee_journal(self):
        pool = Pool()
        Journal = pool.get('account.journal')
        journal, = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        return journal

    def get_contract_from_dunning(self):
        return lambda x: x.contract

    def create_and_post_fee_invoices(self, dunnings):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        journal = self.get_fee_journal()
        fee = self.dunning_fee
        invoices_to_create = []
        contract_invoices_to_create = []
        keyfunc = self.get_contract_from_dunning()
        sorted_dunnings = sorted(dunnings, key=keyfunc)
        for contract, _ in groupby(sorted_dunnings, key=keyfunc):
            if not contract:
                continue
            billing_info = contract.billing_information
            invoice = contract.get_invoice(None, None, billing_info)
            invoice.journal = journal
            invoice.invoice_date = utils.today()
            if not invoice.invoice_address:
                invoice.invoice_address = contract.get_contract_address(
                    invoice.invoice_date)
            invoice.lines = self.get_fee_invoice_lines(fee, contract)
            contract_invoice = ContractInvoice(contract=contract,
                invoice=invoice, non_periodic=True)
            invoices_to_create.append(invoice)
            contract_invoices_to_create.append(contract_invoice)
        if invoices_to_create:
            Invoice.save(invoices_to_create)
            ContractInvoice.save(contract_invoices_to_create)
            Invoice.post(invoices_to_create)

    def process_dunnings(self, dunnings):
        if self.dunning_fee:
            self.create_and_post_fee_invoices(dunnings)
        if self.contract_action == 'terminate':
            self.process_terminate_contracts(dunnings)
        elif self.contract_action == 'hold':
            self.process_hold_contracts(dunnings)
        super(Level, self).process_dunnings(dunnings)

    @staticmethod
    def default_termination_mode():
        return 'at_last_posted_invoice'

    def test(self, line, date):
        res = super(Level, self).test(line, date)
        if not res:
            return res
        if self.skip_level_for_payment and line.payments:
            return False
        if line.contract and line.contract.current_dunning:
            # Do not generate a new dunning for an invoice on a contract
            # with a dunning in progress
            if line.contract.current_dunning.level.sequence > self.sequence:
                return False
        return res

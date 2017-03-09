# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import groupby
from sql import Literal, Window, Null
from sql.aggregate import Min, Max

from trytond.transaction import Transaction
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Dunning',
    'Procedure',
    'Level',
    ]


class Dunning:
    __name__ = 'account.dunning'

    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_line_field', searcher='search_line_field')
    is_contract_main = fields.Function(
        fields.Boolean('Is Main Dunning for Contract'),
        'get_is_contract_main', searcher='search_is_contract_main')

    @classmethod
    def get_is_contract_main(cls, dunnings, name):
        pool = Pool()
        line = pool.get('account.move.line').__table__()
        level = pool.get('account.dunning.level').__table__()
        dunning = cls.__table__()
        cursor = Transaction().connection.cursor()

        contracts = [x.contract.id for x in dunnings]

        # Order by level sequence (it's ok if we assume that the dunning
        # procedure will always be the same for a given contract), then by id
        query_table = dunning.join(line, condition=(dunning.line == line.id)
            & (line.reconciliation == Null) & (line.contract != Null)
            ).join(level, condition=dunning.level == level.id)

        main_dunnings = query_table.select(dunning.id, level.sequence,
            line.contract,
            Max(level.sequence, window=Window([line.contract])).as_('max_seq'),
            where=line.contract.in_(contracts))

        cursor.execute(*main_dunnings.select(Min(main_dunnings.id),
                main_dunnings.contract,
                where=main_dunnings.max_seq == main_dunnings.sequence,
                group_by=main_dunnings.contract))

        per_contract = {}
        for dunning, contract in cursor.fetchall():
            per_contract[contract] = dunning

        return {x.id: not x.contract or per_contract[x.contract.id] == x.id
            for x in dunnings}

    @classmethod
    def search_is_contract_main(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError
        value = value if operator == '=' else not value

        pool = Pool()
        line = pool.get('account.move.line').__table__()
        level = pool.get('account.dunning.level').__table__()
        dunning = cls.__table__()

        query_table = dunning.join(line, condition=(dunning.line == line.id)
            & (line.reconciliation == Null) & (line.contract != Null)
            ).join(level, condition=dunning.level == level.id)

        main_dunnings = query_table.select(dunning.id, level.sequence,
            line.contract,
            Max(level.sequence, window=Window([line.contract])).as_('max_seq'))

        if value:
            return ['OR', ('contract', '=', None),
                ('id', 'in', main_dunnings.select(
                        Min(main_dunnings.id),
                        where=main_dunnings.max_seq == main_dunnings.sequence,
                        group_by=[main_dunnings.contract])),
                ]
        else:
            return [('contract', '!=', None),
                ('id', 'not in', main_dunnings.select(
                        Min(main_dunnings.id),
                        where=main_dunnings.max_seq == main_dunnings.sequence,
                        group_by=[main_dunnings.contract])),
                ]

    @classmethod
    def _overdue_line_domain(cls, date):
        return super(Dunning, cls)._overdue_line_domain(date) + [
            ('payment_amount', '>', 0)]

    @classmethod
    def process(cls, dunnings):
        '''
            This method will filter to treat only the higher level for a
            contract
        '''
        # JCA : If this is too long (in account.dunning.treat batch), maybe set
        # a flag in the context to avoid the test (since it is already
        # performed in the batch query.
        return super(Dunning, cls).process(
            [x for x in dunnings if x.is_contract_main])

    def get_reference_object_for_edm(self, template):
        if not self.contract:
            return super(Dunning, self).get_reference_object_for_edm(template)
        return self.contract

    def get_object_for_contact(self):
        if self.contract:
            return self.contract
        return super(Dunning, self).get_object_for_contact()


class Procedure:
    __name__ = 'account.dunning.procedure'

    from_payment_date = fields.Boolean('Maturity Date From Payment Date',
        help='Maturity date is equal to payment date if defined')


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
    apply_for = fields.Selection([
            ('direct_debit', 'Direct Debit'),
            ('manual', 'Manual'),
            ('all', 'All')], 'Apply For', help='The kind of billing mode '
        'to which this level is applied')
    dunning_fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        domain=[('type', '=', 'fixed')],
        help="A fee invoice will be created. Only for dunnings on contracts.")

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        handler = TableHandler(cls, module_name)
        table = cls.__table__()
        # Migration from 1.4
        migrate = False
        if handler.column_exist('skip_level_for_payment'):
            migrate = True
        super(Level, cls).__register__(module_name)
        if migrate:
            cursor.execute(*table.update(columns=[table.apply_for],
                    values=['manual'], where=(
                        table.skip_level_for_payment == Literal(True))))
            handler.drop_column('skip_level_for_payment')

    @staticmethod
    def default_termination_mode():
        return 'at_last_posted_invoice'

    @staticmethod
    def default_apply_for():
        return 'all'

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
        to_void = []
        termination_reason = SubStatus.get_sub_status(
            'unpaid_premium_termination')
        void_reason = SubStatus.get_sub_status('unpaid_premium_void')
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
            if not date:
                to_void.append(dunning.contract)
            else:
                to_terminate[date].append(dunning.contract)
        for date, contracts in to_terminate.iteritems():
            Contract.terminate(contracts, date, termination_reason)
        if to_void:
            Contract.void(to_void, void_reason)

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
                invoice_type='out',
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

    def get_contract_from_dunning_group(self, dunnings):
        return next((x.contract for x in dunnings if x.contract), None)

    def create_and_post_fee_invoices(self, dunnings):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Contract = pool.get('contract')
        journal = self.get_fee_journal()
        fee = self.dunning_fee
        invoices_to_create = []
        contract_invoices_to_create = []
        keyfunc = self.get_contract_from_dunning()
        sorted_dunnings = sorted(dunnings, key=keyfunc)
        for contract, cur_dunnings in groupby(sorted_dunnings, key=keyfunc):
            contract = self.get_contract_from_dunning_group(cur_dunnings) \
                or contract
            if not contract:
                continue
            billing_info = contract.billing_information
            invoice = contract.get_invoice(None, None, billing_info)
            invoice.journal = journal
            invoice.invoice_date = utils.today()
            if invoice.invoice_address is None:
                invoice.invoice_address = contract.get_contract_address(
                    invoice.invoice_date)
            invoice.lines = self.get_fee_invoice_lines(fee, contract)
            contract_invoice = ContractInvoice(contract=contract,
                invoice=invoice, non_periodic=True)
            invoices_to_create.append(invoice)
            contract_invoices_to_create.append(contract_invoice)
        if invoices_to_create:
            Contract._finalize_invoices(contract_invoices_to_create)
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

    def test(self, line, date):
        res = super(Level, self).test(line, date)
        direct_debit = line.payment_date or line.payments
        if not res:
            return res
        if self.apply_for == 'direct_debit' and not direct_debit:
            return False
        if self.apply_for == 'manual' and direct_debit:
            return False
        if line.contract and line.contract.current_dunning:
            # Do not generate a new dunning for an invoice on a contract
            # with a dunning in progress
            if line.contract.current_dunning.level.sequence > self.sequence:
                return False
        return res

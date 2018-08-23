# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pyson import Bool, Eval, If
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.config import config

from trytond.modules.coog_core import fields, utils

__all__ = [
    'Move',
    'MoveLine',
    'ReconcileShow',
    'Reconcile',
    ]


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.kind.selection.append(('invoice_posting', 'Invoice Posting'))
        cls.kind.selection.append(
            ('invoice_cancellation', 'Invoice Cancellation'))

    def get_kind(self, name):
        if self.origin:
            if self.origin.__name__ == 'account.invoice':
                return 'invoice_posting'
            elif self.origin_item.__name__ == 'account.invoice':
                return 'invoice_cancellation'
        return super(Move, self).get_kind(name)

    def get_icon(self, name):
        if self.kind == 'invoice_posting':
            return 'invoice'
        elif self.kind == 'invoice_cancellation':
            return 'invoice_cancel'
        return super(Move, self).get_icon(name)


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    contract = fields.Many2One('contract', 'Contract', select=True,
        ondelete='RESTRICT', readonly=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('contract')

    @classmethod
    def __register__(cls, module):
        # Migration from 1.3 : Add contract field
        # First, detect if a migration will be needed
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        do_migrate = False
        if TableHandler.table_exist('account_move_line'):
            line_table = TableHandler(cls)
            if not line_table.column_exist('contract'):
                do_migrate = True
        super(MoveLine, cls).__register__(module)
        # Migrate from 1.3 : second step
        if not do_migrate:
            return
        if config.getboolean('env', 'testing') is True:
            # necessary because the migration script
            # uses Window function not supported by sqlite
            return
        # Do migrate
        cursor.execute('''
-- Set contrat for move lines originating from a contract invoice

UPDATE
    account_move_line AS line
SET
    contract = ctr_invoice.contract
FROM
    account_invoice AS invoice,
    contract_invoice AS ctr_invoice
WHERE
    (line.move = invoice.move OR
        line.move = invoice.cancel_move) AND
    ctr_invoice.invoice = invoice.id
;

-- Propagate to lines which were reconciliated with those lines
UPDATE
    account_move_line line_to_update
SET
    contract = tmp_table.max_ctr
FROM (
    SELECT
        line.id, line.reconciliation, line.contract,
        COUNT(line.reconciliation) OVER (PARTITION BY line.reconciliation) AS
            nbr_reco,
        COUNT(line.contract) OVER (PARTITION BY line.reconciliation) AS
            nbr_ctr,
        MAX(line.contract) OVER (PARTITION BY line.reconciliation) AS max_ctr,
        MIN(line.contract) OVER (PARTITION BY line.reconciliation) AS min_ctr
    FROM
        account_move_line AS line
    WHERE
        line.reconciliation IS NOT NULL
    ORDER BY
        line.reconciliation
    ) tmp_table
WHERE
    tmp_table.nbr_reco > tmp_table.nbr_ctr AND
    tmp_table.min_ctr = tmp_table.max_ctr AND
    line_to_update.id = tmp_table.id
;
        ''')

    @classmethod
    def write(cls, *args):
        '''
            Check for reconciliation creations, and propagate the 'contract'
            attribute if it exists on at least one of the affected lines.

            This takes advantage of the fact that the write corresponding to
            a new reconciliation will translate to a :
                write(lines, {'reconciliation': my_reco_id})
            call, which we can detect.

            Another option would be to intercept the reconciliation creation,
            and convert the "add" part of the creation dict to a add + update,
            but this is easier to read / maintain.
        '''
        actions = iter(args)
        for lines, values in zip(actions, actions):
            if 'reconciliation' not in values:
                continue
            if 'contract' in values:
                continue
            contract, to_update = None, False
            for line in lines:
                if not line.contract:
                    to_update = True
                    continue
                if contract and line.contract == contract:
                    continue
                if contract:
                    # Only write contract if only one contract in the current
                    # reconciliation
                    break
                contract = line.contract
            else:
                if contract and to_update:
                    values['contract'] = contract
        super(MoveLine, cls).write(*args)

    @classmethod
    def init_payments(cls, lines, journal):
        valid_lines = []
        for line in lines:
            contract = line.contract
            if not contract:
                valid_lines.append(line)
                continue
            billing_information = contract.billing_information
            if not billing_information:
                valid_lines.append(line)
                continue
            if (not billing_information.suspended or (
                        billing_information.suspended and
                        not journal.apply_payment_suspension)):
                valid_lines.append(line)

        return super(MoveLine, cls).init_payments(valid_lines, journal)

    def split(self, amount_to_split, journal=None):
        split_move = super(MoveLine, self).split(amount_to_split, journal)
        if self.contract:
            for line in split_move.lines:
                line.contract = self.contract
        return split_move


class ReconcileShow:
    __metaclass__ = PoolMeta
    __name__ = 'account.reconcile.show'

    remaining_repartition_method = fields.Selection([
            ('write_off', 'Write Off'),
            ('set_on_party', 'Set on Party'),
            ('set_on_contract', 'Set on Contract')
            ],
        'Remaining Repartition Method', states={
            'required': Bool(Eval('write_off', False)),
            'invisible': If(~Eval('write_off', 0), 0,
                Eval('write_off', 0)) >= 0
            },
        depends=['write_off'])
    repartition_method_string = remaining_repartition_method.translated(
        'remaining_repartition_method')
    contract = fields.Many2One('contract', 'Contract',
        domain=[('subscriber', '=', Eval('party'))],
        states={
            'required':
                Eval('remaining_repartition_method', '') == 'set_on_contract',
            'invisible':
                Eval('remaining_repartition_method', '') != 'set_on_contract',
            },
        depends=['party', 'remaining_repartition_method'])

    @classmethod
    def __setup__(cls):
        super(ReconcileShow, cls).__setup__()
        cls.journal.domain = [If(
                Eval('remaining_repartition_method', '') == 'write_off',
                cls.journal.domain,
                [('type', '=', 'split')])]
        cls.journal.depends.append('remaining_repartition_method')

    @classmethod
    def default_date(cls):
        return utils.today()

    @classmethod
    def default_remaining_repartition_method(cls):
        return 'set_on_party'

    @fields.depends('contract', 'description', 'journal', 'lines', 'party',
        'remaining_repartition_method', 'write_off')
    def on_change_lines(self):
        if not self.lines:
            return
        self.write_off = self.on_change_with_write_off()
        self.on_change_write_off()

    @fields.depends('contract', 'description', 'journal', 'party',
        'remaining_repartition_method', 'repartition_method_string')
    def on_change_remaining_repartition_method(self):
        pool = Pool()
        Contract = pool.get('contract')
        Journal = pool.get('account.journal')
        if self.remaining_repartition_method != 'set_on_contract':
            self.contract = None
        else:
            possible_contracts = Contract.search(
                [('subscriber', '=', self.party.id)])
            if len(possible_contracts) == 1:
                self.contract = possible_contracts[0]
        if self.remaining_repartition_method != 'write_off':
            self.journal = Journal.get_default_journal('split')
        else:
            self.journal = Journal.get_default_journal('write-off')
        self.description = '%s - %s' % (self.repartition_method_string,
            self.contract.rec_name if self.contract
            else self.party.rec_name if self.party else '')

    @fields.depends('contract', 'journal', 'party',
        'remaining_repartition_method', 'write_off')
    def on_change_write_off(self):
        if self.write_off >= 0:
            self.contract = None
            self.remaining_repartition_method = 'write_off'
        else:
            self.remaining_repartition_method = 'set_on_party'
        self.on_change_remaining_repartition_method()
        if not self.write_off:
            # Set journal to avoid 0.0 write_off line creation
            self.journal = None


class Reconcile:
    __metaclass__ = PoolMeta
    __name__ = 'account.reconcile'

    def transition_reconcile(self):
        self.prepare_reconciliation()
        return super(Reconcile, self).transition_reconcile()

    def prepare_reconciliation(self):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        if self.show.remaining_repartition_method == 'write_off':
            return
        if not self.show.lines:
            return
        to_write_off = self.show.account.currency.round(self.show.write_off)
        if not to_write_off:
            return
        period_id = Period.find(self.show.account.company.id,
            date=self.show.date)

        move = Move()
        move.journal = self.show.journal
        move.period = Period(period_id)
        move.date = self.show.date
        move.description = self.show.description

        # Line 1 is the line that will be used to balance the reconciliation
        line1 = Line()
        line1.account = self.show.account
        line1.party = self.show.party
        if to_write_off > 0:
            line1.credit = to_write_off
            line1.debit = 0
        else:
            line1.credit = 0
            line1.debit = -to_write_off

        # Line 2 will be the remaining line after reconciliation
        line2 = Line()
        line2.account = self.show.account
        line2.party = self.show.party
        if to_write_off > 0:
            line2.credit = 0
            line2.debit = to_write_off
        else:
            line2.credit = -to_write_off
            line2.debit = 0
        if self.show.remaining_repartition_method == 'set_on_contract':
            line2.contract = self.show.contract

        move.lines = [line1, line2]
        move.save()
        Move.post([move])
        self.show.lines = list(self.show.lines) + [move.lines[1]]


class Reconciliation:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.reconciliation'

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        PaymentSuspension = pool.get('contract.payment_suspension')
        BillingInformation = pool.get('contract.billing_information')
        reconciliations = super(Reconciliation, cls).create(vlist)
        line_ids = set()
        for reconciliation in reconciliations:
            line_ids |= {l.id for l in reconciliation.lines}
        inactive_suspensions = PaymentSuspension.search([('payment_line_due',
                    'in', list(line_ids)), ('active', '=', False)])
        unsuspended = [x.billing_info for x in inactive_suspensions
            if not x.billing_info.suspended]
        if unsuspended:
            BillingInformation.update_after_unsuspend(unsuspended)
        return reconciliations

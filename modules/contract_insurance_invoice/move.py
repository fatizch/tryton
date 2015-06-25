from trytond import backend
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Move',
    'MoveLine',
    ]


class Move:
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
    __name__ = 'account.move.line'

    contract = fields.Many2One('contract', 'Contract', select=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('contract')

    @classmethod
    def __register__(cls, module):
        # Migration from 1.3 : Add contract field
        # First, detect if a migration will be needed
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        do_migrate = False
        if TableHandler.table_exist(cursor, 'account_move_line'):
            line_table = TableHandler(cursor, cls)
            if not line_table.column_exist('contract'):
                do_migrate = True
        super(MoveLine, cls).__register__(module)
        # Migrate from 1.3 : second step
        if not do_migrate:
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

    def split(self, amount_to_split, journal=None):
        split_move = super(MoveLine, self).split(amount_to_split, journal)
        if self.contract:
            for line in split_move.lines:
                line.contract = self.contract
        return split_move

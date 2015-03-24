from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import export, fields, utils

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    ]


class Line(export.ExportImportMixin):
    'Account Move Line'
    __name__ = 'account.move.line'

    account_kind = fields.Function(
        fields.Char('Account Kind'), 'get_account_kind')
    reconciliation_lines = fields.Function(
        fields.One2Many('account.move.line', 'reconciliation_lines',
            'Reconciliation Lines'),
        'get_reconciliation_lines')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'), 'get_currency_symbol')

    def get_synthesis_rec_name(self, name):
        if self.origin:
            if (getattr(self.origin, 'get_synthesis_rec_name', None)
                    is not None):
                return self.origin.get_synthesis_rec_name(name)
            return self.origin.get_rec_name(name)
        return self.get_rec_name(name)

    def get_reconciliation_lines(self, name):
        if self.reconciliation is None:
            return
        return[line.id for line in self.reconciliation.lines]

    def get_currency_symbol(self, name):
        return self.account.currency.symbol if self.account else ''

    def get_icon(self, name=None):
        if self.reconciliation:
            return 'coopengo-reconciliation'

    def get_account_kind(self, name):
        return self.account.kind if self.account else ''

    @classmethod
    def split_lines(cls, splits, journal=None):
        # splits is a list of line / split_amount tuples :
        # Line.split_lines([line1, split1), (line2, split2)], journal=...)
        if not splits:
            return []
        pool = Pool()
        Move = pool.get('account.move')
        split_moves = {}
        split_amounts = {}
        for line, amount_to_split in splits:
            split_amounts[line] = amount_to_split
            split_moves[line] = line.split(amount_to_split, journal)
        Move.save(split_moves.values())
        Move.post(split_moves.values())
        split_lines = {}
        for source_line, split_move in split_moves.iteritems():
            # Order of move.lines may not always be keep after saving / posting
            split_amount = split_amounts[source_line]
            split, remaining, compensation = None, None, None
            for line in split_move.lines:
                if abs(line.amount) == abs(source_line.amount):
                    compensation = line
                elif abs(line.amount) == split_amount:
                    split = line
                else:
                    remaining = line
            split_lines[source_line] = (split, remaining, compensation)
        return split_lines

    def split(self, amount_to_split, journal=None):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Journal = pool.get('account.journal')

        if journal is None:
            journal = Journal.search([('type', '=', 'split')])[0]

        split_move = Move(journal=journal, company=self.move.company,
            date=utils.today())
        split, remaining, compensation = [
            Line(party=self.party, account=self.account, credit=0, debit=0),
            Line(party=self.party, account=self.account, credit=0, debit=0),
            Line(party=self.party, account=self.account, credit=0, debit=0),
            ]

        if self.credit and self.credit > 0 or self.debit and self.debit < 0:
            base = self.credit - self.debit
            source, dest = 'credit', 'debit'
        else:
            base = self.debit - self.credit
            source, dest = 'debit', 'credit'

        assert amount_to_split < base
        setattr(split, source, amount_to_split)
        setattr(remaining, source, base - amount_to_split)
        setattr(compensation, dest, base)
        split_move.lines = [split, remaining, compensation]
        return split_move

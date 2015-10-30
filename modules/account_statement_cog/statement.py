from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, export

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    'Statement',
    ]


class Line:
    'Account Statement Line'
    __name__ = 'account.statement.line'

    in_bank_deposit_ticket = fields.Function(
        fields.Boolean('In Bank Deposit Ticket'),
        'on_change_with_in_bank_deposit_ticket')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.number.depends += ['in_bank_deposit_ticket']
        cls.number.states['required'] = Bool(Eval('in_bank_deposit_ticket'))

    @fields.depends('statement')
    def on_change_statement(self):
        self.in_bank_deposit_ticket = \
            self.on_change_with_in_bank_deposit_ticket()

    @fields.depends('statement')
    def on_change_with_in_bank_deposit_ticket(self, name=None):
        return self.statement and self.statement.in_bank_deposit_ticket

    def get_synthesis_rec_name(self, name):
        return '%s - %s - %s' % (self.statement.journal.rec_name,
            Pool().get('ir.date').date_as_string(self.date),
            self.statement.journal.currency.amount_as_string(self.amount))

    def create_move(self):
        move = super(Line, self).create_move()
        if move:
            move.description = (self.description
                if self.description else self.statement.journal.rec_name)
            move.save()
        return move

    def get_move_line(self):
        move_line = super(Line, self).get_move_line()
        if not move_line.description and self.number:
            move_line.description = self.number
        return move_line


class Statement(export.ExportImportMixin):
    __name__ = 'account.statement'
    _func_key = 'name'

    in_bank_deposit_ticket = fields.Function(
        fields.Boolean('In Bank Deposit Ticket'),
        'on_change_with_in_bank_deposit_ticket',
        searcher='search_in_bank_deposit_ticket')
    total_statement_amount = fields.Function(
        fields.Numeric('Total Amount'),
        'get_total_statement_amount')

    @classmethod
    def __setup__(cls):
        super(Statement, cls).__setup__()
        cls.lines.depends.append('in_bank_deposit_ticket')
        cls.name.readonly = True

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Journal = pool.get('account.statement.journal')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('name'):
                journal_id = vals.get('journal')
                journal = Journal(journal_id)
                vals['name'] = Sequence.get_id(journal.sequence.id)
        return super(Statement, cls).create(vlist)

    @fields.depends('journal')
    def on_change_with_in_bank_deposit_ticket(self, name=None):
        return self.journal and self.journal.bank_deposit_ticket_statement

    def on_change_lines(self):
        # Workaround for issue #2743 : assume that we are in a recursion if
        # last line amount is None
        if self.lines and self.lines[-1].amount is None:
            return
        super(Statement, self).on_change_lines()

    def get_total_statement_amount(self, name):
        return sum(l.amount for l in self.lines)

    @classmethod
    def search_in_bank_deposit_ticket(cls, name, clause):
        return [('journal.bank_deposit_ticket_statement',) + tuple(clause[1:])]

    @classmethod
    def validate_manual(cls):
        pass

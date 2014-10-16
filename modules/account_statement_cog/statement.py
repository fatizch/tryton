from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields

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

    @fields.depends('statement')
    def on_change_statement(self):
        return {'in_bank_deposit_ticket':
            self.on_change_with_in_bank_deposit_ticket()}

    @fields.depends('statement')
    def on_change_with_in_bank_deposit_ticket(self, name=None):
        return self.statement and self.statement.in_bank_deposit_ticket

    def get_synthesis_rec_name(self, name):
        return '%s - %s - %s' % (self.statement.journal.rec_name,
            Pool().get('ir.date').date_as_string(self.date),
            self.statement.journal.currency.amount_as_string(self.amount))


class Statement:
    __name__ = 'account.statement'

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

    def get_total_statement_amount(self, name):
        return sum(l.amount for l in self.lines)

    @classmethod
    def search_in_bank_deposit_ticket(cls, name, clause):
        return [('journal.bank_deposit_ticket_statement',) + tuple(clause[1:])]

    @classmethod
    def validate_manual(self):
        pass

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Unique
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, export, model, coop_string

__metaclass__ = PoolMeta

__all__ = [
    'Journal',
    'CancelMotive',
    'JournalCancelMotiveRelation',
    ]


class Journal(export.ExportImportMixin):
    __name__ = 'account.statement.journal'
    _func_key = 'name'

    bank_deposit_ticket_statement = fields.Boolean(
        'Bank Deposit Ticket Statement')
    sequence = fields.Many2One('ir.sequence', 'Statement Sequence',
        required=True, domain=[('code', '=', 'statement')])
    cancel_motives = fields.Many2Many(
        'statement.journal-statement.journal.cancel_motive',
        'journal', 'motive', 'Cancel Motives')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.validation.selection.append(('manual', 'Manual'))
        cls._error_messages.update({
                'cancel_journal_mixin': 'You can not cancel two statements '
                'with different statement journals',
                })

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'currency', 'company'}


class CancelMotive(model.CoopSQL, model.CoopView):
    'Statement Journal Cancel Motives'

    __name__ = 'account.statement.journal.cancel_motive'
    _func_key = 'code'

    code = fields.Char('Code', required=True, select=True)
    name = fields.Char('Description', required=True, translate=True)
    journals = fields.Many2Many(
        'statement.journal-statement.journal.cancel_motive',
        'motive', 'journal', 'journals')

    @classmethod
    def __setup__(cls):
        super(CancelMotive, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [('code_unique', Unique(t, t.code),
                'The code must be unique'),
                ]

    @classmethod
    def _export_skips(cls):
        return super(CancelMotive, cls)._export_skips() | {'journals'}

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class JournalCancelMotiveRelation(model.CoopSQL, model.CoopView):
    'Journal - Statement Journal Cancel Motives'

    __name__ = 'statement.journal-statement.journal.cancel_motive'

    motive = fields.Many2One('account.statement.journal.cancel_motive',
        'Cancel motive', ondelete='RESTRICT', select=True, required=True)
    journal = fields.Many2One('account.statement.journal', 'Journal',
        ondelete='CASCADE', select=True, required=True)

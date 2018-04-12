# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import Unique
from trytond.transaction import Transaction

from sql import Literal, Null
from sql.operators import NotIn

from trytond.modules.coog_core import fields, export, model, coog_string


__all__ = [
    'Journal',
    'CancelMotive',
    'JournalCancelMotiveRelation',
    ]


class Journal(export.ExportImportMixin):
    __name__ = 'account.statement.journal'
    _func_key = 'name'

    sequence = fields.Many2One('ir.sequence', 'Statement Sequence',
        required=True, domain=[('code', '=', 'statement')])
    cancel_motives = fields.Many2Many(
        'statement.journal-statement.journal.cancel_motive',
        'journal', 'motive', 'Cancel Motives')
    process_method = fields.Selection('get_process_methods',
        'Process Method')
    auto_post = fields.Boolean('Auto Post Statement', help='If set, '
        'the statement wizard will automatically validate and post created '
        'statement')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        cheque_ids = []
        journal_h = TableHandler(cls, module_name)
        has_bank_desposit_ticket_statement = journal_h.column_exist(
                'bank_deposit_ticket_statement')
        if has_bank_desposit_ticket_statement:
            cursor.execute(*table.select(table.id,
                    where=table.bank_deposit_ticket_statement == Literal(True)
                    ))
            cheque_ids = [x for x, in cursor.fetchall()]
        super(Journal, cls).__register__(module_name)
        # migraton from 1.10
        if has_bank_desposit_ticket_statement:
            where_clause = (table.process_method == Null)
            if cheque_ids:
                where_clause &= NotIn(table.id, cheque_ids)
            cursor.execute(*table.update(
                    columns=[table.process_method],
                    values=[Literal('other')],
                    where=where_clause,
                    ))
            if cheque_ids:
                cursor.execute(*table.update(
                    columns=[table.process_method],
                    values=[Literal('cheque')],
                    where=table.id.in_(cheque_ids)))
            journal_h.drop_column('bank_deposit_ticket_statement')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.validation.selection.append(('manual', 'Manual'))
        cls._error_messages.update({
                'cancel_journal_mixin': 'You can not cancel two statements '
                'with different statement journals',
                'method_cheque': 'Cheque',
                'method_other': 'Other',
                })

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'currency', 'company'}

    @classmethod
    def get_process_methods(cls):
        return [('cheque', cls.raise_user_error('method_cheque',
                    raise_exception=False)),
                ('other', cls.raise_user_error('method_other',
                    raise_exception=False))]

    @staticmethod
    def default_auto_post():
        return False


class CancelMotive(model.CoogSQL, model.CoogView):
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
        return coog_string.slugify(self.name)


class JournalCancelMotiveRelation(model.CoogSQL, model.CoogView):
    'Journal - Statement Journal Cancel Motives'

    __name__ = 'statement.journal-statement.journal.cancel_motive'

    motive = fields.Many2One('account.statement.journal.cancel_motive',
        'Cancel motive', ondelete='RESTRICT', select=True, required=True)
    journal = fields.Many2One('account.statement.journal', 'Journal',
        ondelete='CASCADE', select=True, required=True)

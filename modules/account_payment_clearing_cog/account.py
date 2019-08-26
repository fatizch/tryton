# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond import backend
from trytond.transaction import Transaction


__all__ = [
    'Journal',
    ]


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    @classmethod
    def __register__(cls, module_name):
        # Migration from 2.2
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        journal_table = TableHandler(cls)
        journal = cls.__table__()
        do_migrate = False
        if journal_table.column_exist('aggregate_posting'):
            do_migrate = True
        super(Journal, cls).__register__(module_name)
        if do_migrate:
            cursor.execute(*journal.update(
                    columns=[journal.aggregate_posting_behavior],
                    values=['except_payment_cancel'],
                    where=(
                        journal.aggregate_posting == Literal(True))))
            journal_table.drop_column('aggregate_posting')

    @classmethod
    def get_aggregate_posting_options(cls):
        options = super(Journal, cls).get_aggregate_posting_options()
        return options + [('except_payment_cancel', gettext(
                    'account_payment_clearing_cog.msg_except_payment_cancel'))]

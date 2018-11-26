# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from sql import Table

from trytond import backend
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


__all__ = [
    'Journal',
    ]


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    @classmethod
    def __register__(cls, module_name):
        super(Journal, cls).__register__(module_name)
        # Migration from 4.8 : create a payment method for each journal
        # of type 'cash'
        TableHandler = backend.get('TableHandler')
        if not TableHandler.table_exist('account_journal_account'):
            return
        journal = cls.__table__()
        payment_method = Table('account_invoice_payment_method')
        journal_account = Table('account_journal_account')
        cursor = Transaction().connection.cursor()
        cursor.execute(*payment_method.select(payment_method.id))
        res = list(cursor.fetchall())
        if res:
            return
        cursor.execute(*journal_account.join(journal,
                condition=((journal_account.journal == journal.id) & (
                        journal.type == 'cash'))
                ).select(
                    journal_account.company,
                    journal.name,
                    journal_account.journal,
                    journal_account.credit_account,
                    journal_account.debit_account))
        res = cursor.fetchall()
        now = datetime.datetime.now()
        payment_method_insert_cols = [
            payment_method.company,
            payment_method.name,
            payment_method.journal,
            payment_method.credit_account,
            payment_method.debit_account,
            payment_method.create_uid,
            payment_method.create_date,
            payment_method.active,
        ]
        for company, journal_name, journal, credit_account, \
                debit_account in res:
            cursor.execute(*payment_method.insert(
                    payment_method_insert_cols, [[company, journal_name,
                            journal, credit_account, debit_account, 0, now,
                            True]]))
        # End of migration from 4.8

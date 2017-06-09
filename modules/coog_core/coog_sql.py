# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.functions import Function as SqlFunction


class TextCat(SqlFunction):
    '''
        Use the textcat function of postgresql to index reference joins:
            Concat('account.invoice,', Cast(invoice.id, 'VARCHAR'))

        Becomes:
            TextCat('account.invoice,', Cast(invoice.id, 'VARCHAR'))

        The associated index would be:
            CREATE INDEX account_invoice_ref_idx ON account_invoice
                USING btree (textcat('account.invoice,', CAST(id AS VARCHAR)))

    '''
    __slots__ = ()
    _function = 'textcat'

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'CreateInvoicePrincipalAsk',
    ]


class CreateInvoicePrincipalAsk:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_invoice_principal.ask'

    @classmethod
    def __setup__(cls):
        super(CreateInvoicePrincipalAsk, cls).__setup__()
        cls.notice_kind.selection.append(('benefits', 'Benefit'))

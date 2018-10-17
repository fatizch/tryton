# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'InvoiceSlipConfiguration',
    'Invoice',
    ]


class InvoiceSlipConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def __setup__(cls):
        super(InvoiceSlipConfiguration, cls).__setup__()
        cls.slip_kind.selection.append(
            ('pasrau', 'Pasrau'))

    @classmethod
    def _event_code_from_slip_kind(cls, slip_kind):
        if slip_kind == 'pasrau':
            return 'pasrau_slips_generated'
        return cls._event_code_from_slip_kind(slip_kind)


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection.append(('pasrau', 'Pasrau'))

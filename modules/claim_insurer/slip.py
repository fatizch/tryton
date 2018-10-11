# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'InvoiceSlipConfiguration',
    ]


class InvoiceSlipConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def _get_invoice_type(cls, parameters):
        if parameters['slip_kind'] == 'claim_insurer_invoice':
            return 'out'
        return super(InvoiceSlipConfiguration,
            cls)._get_invoice_type(parameters)

    @classmethod
    def _event_code_from_slip_kind(cls, slip_kind):
        if slip_kind == 'claim_insurer_invoice':
            return 'commission_invoice_generated'
        return super(InvoiceSlipConfiguration,
            cls)._event_code_from_slip_kind(slip_kind)

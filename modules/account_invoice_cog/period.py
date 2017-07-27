# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


__all__ = [
    'Period',
    ]


class Period:
    __metaclass__ = PoolMeta
    __name__ = 'account.period'

    def get_invoice_sequence(self, invoice_type):
        invoice_sequences = self.fiscalyear.invoice_sequences
        pattern = {
            'fiscalyear': self.fiscalyear.id,
            'period': self.id,
            'company': self.fiscalyear.company.id,
            }
        for sequence in invoice_sequences:
            if sequence.match(pattern):
                return getattr(sequence, invoice_type + '_sequence')

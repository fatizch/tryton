# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'PaymentAcknowledgeBatch',
    ]


class PaymentAcknowledgeBatch:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.acknowledge'

    @classmethod
    def payment_invalid(cls, payment):
        return (payment.state == 'processing'
            and payment.journal.process_method != 'paybox')

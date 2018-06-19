# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import model

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    def insurer_reporting_lines(self, **kwargs):
        domain = [
            ('amount', '!=', 0),
            ('invoice_line.invoice', '=', self),
            ]
        return model.order_data_stream(
            model.search_and_stream(Pool().get('commission'), domain,
                **kwargs),
            lambda x: x.commissioned_contract.id if x.commissioned_contract
            else None)

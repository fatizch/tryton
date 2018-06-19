# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields, model

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    report_commissions = fields.Function(
        fields.One2Many('commission', None, 'Commissions To Report'),
        'get_report_commissions')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        logger = logging.getLogger('trytond.fields')
        logger.warning('[DEPRECATION WARNING]: Field report_commissions will '
            'be removed as of version 2.2')

    def get_report_commissions(self, name):
        good_lines = [x for x in self.lines if x.from_commissions and x.amount]
        commissions = [x for good_line in good_lines
            for x in good_line.from_commissions]
        commissions.sort(key=lambda x: x.commissioned_contract.id)
        commissions = [x.id for x in commissions]
        return commissions

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

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import utils

__all__ = [
    'MoveLine',
    ]


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @property
    def rule_pattern(self):
        pattern = super().rule_pattern
        InvoiceLine = Pool().get('account.invoice.line')
        MoveLine = Pool().get('account.move.line')
        if self.origin and isinstance(self.origin, (InvoiceLine, MoveLine)):
            if isinstance(self.origin, InvoiceLine):
                origin_invoice_line = self.origin
            elif isinstance(self.origin, MoveLine):
                origin_invoice_line = self.origin.origin
            date = origin_invoice_line.get_analytic_extra_data_match_date()
            version_at_date = utils.get_good_version_at_date(self.contract,
                'extra_datas', date, start_var_name='date') if self.contract \
                else None
            if version_at_date:
                pattern['extra_data'] = version_at_date.extra_data_values
            pattern.setdefault('extra_data', {}).update(
                origin_invoice_line.get_extra_data_for_analytic_match())
        return pattern

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Contract',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    def get_invoice(self, start, end, billing_information):
        invoice = super(Contract, self).get_invoice(start, end,
            billing_information)
        invoice.product = self.product
        return invoice

    def _find_insurer_agent_domain(self, coverage, date):
        domain = super(Contract, self)._find_insurer_agent_domain(
            coverage, date)
        coverage = None
        if coverage and getattr(coverage, 'products', None):
            domain.append(('insurer.product', '=', coverage.products[0].id))
        return domain

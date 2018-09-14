# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Contract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    def get_invoice(self, start, end, billing_information):
        invoice = super(Contract, self).get_invoice(start, end,
            billing_information)
        invoice.product = self.product
        return invoice

    def find_insurer_agent_domain(self, option=None, line=None):
        domain = super(Contract, self).find_insurer_agent_domain(option, line)
        coverage = None
        if not option and line and getattr(line, 'details', None):
            coverage = getattr(line.details[0], 'rated_entity', None)
        elif option:
            coverage = option.coverage
        if coverage and getattr(coverage, 'products', None):
            domain.append(('insurer.product', '=', coverage.products[0].id))
        return domain

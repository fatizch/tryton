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
        if not option and line:
            coverage = getattr(line.details[0], 'rated_entity', None)
        if option:
            coverage = option.coverage
        product, = coverage.products
        domain.append(('insurer.product', '=', product.id))
        return domain

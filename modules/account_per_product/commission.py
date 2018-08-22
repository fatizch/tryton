# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'Commission',
    'Agent',
    'PlanLines',
    ]


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    def _group_to_invoice_key(self):
        key = super(Commission, self)._group_to_invoice_key()
        if self.commissioned_contract:
            key += (('product', self.commissioned_contract.product))
        return key

    @classmethod
    def _get_invoice(cls, key):
        invoice = super(Commission, cls)._get_invoice(key)
        invoice.product = key['product']
        return invoice

    @classmethod
    def get_insurer_invoice(cls, company, insurer, journal, date, fname):
        invoice = super(Commission, cls).get_insurer_invoice(company, insurer,
            journal, date, fname)
        invoice.product = insurer.product
        return invoice


class Agent:
    __metaclass__ = PoolMeta
    __name__ = 'commission.agent'

    def get_rec_name(self, name):
        name = super(Agent, self).get_rec_name(name)
        if not self.insurer:
            return name
        return '[%s] %s' % (self.insurer.product.code, name)

    def get_commissioned_products(self, name):
        product_ids = super(Agent, self).get_commissioned_products(name)
        if not self.insurer:
            return product_ids
        return [i for i in product_ids if i == self.insurer.product.id]

    @classmethod
    def search_commissioned_products(cls, name, clause):
        return ['OR',
            [('plan.commissioned_products',) + tuple(clause[1:]),
                ('insurer', '=', None)],
            [('insurer.product',) + tuple(clause[1:])]
            ]


class PlanLines:
    __metaclass__ = PoolMeta
    __name__ = 'commission.plan.line'

    def get_cache_key(self, coverage_id, pattern):
        key = super(PlanLines, self).get_cache_key(coverage_id, pattern)
        agent_id = pattern['agent'].id if pattern['agent'].insurer else None
        return key + (agent_id,)

    def get_option_ids(self, pattern):
        agent_id = pattern['agent'].id if pattern['agent'].insurer else None
        ins_product = pattern['agent'].insurer.product if agent_id else None
        return {o.id for o in self.options if not agent_id
            or o in ins_product.coverages}

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields


__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    agents = fields.Function(
        fields.Many2Many('commission.agent', None, None, 'Agents'),
        'get_agents')

    def get_agents(self, name=None):
        agents = []
        for coverage in self.coverages:
            agents += coverage.agents
        return [a.id for a in agents]


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    commission_plan_lines = fields.Many2Many(
        'commission.plan.lines-offered.option.description', 'option',
        'plan_line', 'Commission Plan Lines')
    agents = fields.Function(
        fields.Many2Many('commission.agent', None, None, 'Agents'),
        'get_agents')

    @classmethod
    def _export_skips(cls):
        return super(OptionDescription, cls)._export_skips() | {
            'commission_plan_lines'}

    @classmethod
    def copy(cls, coverages, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('commission_plan_lines', None)
        return super(OptionDescription, cls).copy(coverages, default=default)

    def get_domain_agents(self):
        return [
            ('plan', 'in', [p.id for p in [l.plan
                        for l in self.commission_plan_lines]]),
            ]

    def get_agents(self, name=None):
        Agent = Pool().get('commission.agent')
        return [a.id for a in Agent.search(self.get_domain_agents())]

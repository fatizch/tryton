import copy

from trytond.pool import Pool, PoolMeta
from trytond.modules.coop_utils import model, fields, export

__all__ = [
    'DistributionNetwork',
    'DistributionNetworkComPlanRelation',
    'DistributionNetworkBrokerRelation',
    ]


class DistributionNetwork():
    'Distribution Network'

    __name__ = 'distribution.dist_network'
    __metaclass__ = PoolMeta

    commission_plans = fields.Many2Many('distribution.dist_network-plan',
        'dist_network', 'com_plan', 'Commission Plans',
        domain=[('kind', '=', 'commission')])
    parent_com_plans = fields.Function(
        fields.Many2Many('offered.product', None, None,
            'Top Level Commission Plans'),
        'get_parent_com_plans_id')
    all_com_plans = fields.Function(
        fields.Many2Many('offered.product', None, None,
            'Top Level Commission Plans'),
        'get_all_com_plans_id')
    brokers = fields.Many2Many('distribution.dist_network-broker',
        'dist_network', 'broker', 'Brokers',
        domain=[('is_broker', '=', True)])
    childs_brokers = fields.Function(
        fields.Many2Many('party.party', None, None, 'Sub Level Brokers',),
        'get_childs_brokers_id')

    @classmethod
    def __setup__(cls):
        super(DistributionNetwork, cls).__setup__()
        cls.brokers = copy.copy(cls.brokers)
        cls.brokers.domain = export.clean_domain_for_import(
            cls.brokers.domain)

    def get_parent_com_plans_id(self, name):
        Plan = Pool().get('offered.product')
        return [x.id for x in Plan.search([
                    ('kind', '=', 'commission'),
                    ('dist_networks.left', '<', self.left),
                    ('dist_networks.right', '>', self.right),
                ])
            ]

    def get_childs_brokers_id(self, name):
        Broker = Pool().get('party.party')
        return [x.id for x in Broker.search([
                    ('dist_networks.parent', 'child_of', self.id),
                    ('dist_networks.id', '!=', self.id),
                    ])
            ]

    def get_all_com_plans_id(self, name):
        return [x.id for x in self.commission_plans + self.parent_com_plans]

    def get_brokers(self):
        return self.brokers + self.childs_brokers


class DistributionNetworkComPlanRelation(model.CoopSQL):
    'Relation Distribution Network - Commission Plan'

    __name__ = 'distribution.dist_network-plan'

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network', ondelete='CASCADE')
    com_plan = fields.Many2One('offered.product', 'Commission Plan',
        ondelete='RESTRICT')


class DistributionNetworkBrokerRelation(model.CoopSQL, model.CoopView):
    'Relation Distribution Network - Broker'

    __name__ = 'distribution.dist_network-broker'

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network', ondelete='RESTRICT')
    broker = fields.Many2One('party.party', 'Broker', ondelete='CASCADE')

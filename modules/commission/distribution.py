from trytond.pool import PoolMeta
from trytond.modules.coop_utils import model, fields

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
        'dist_network', 'com_plan', 'Commission Plans')
    parent_com_plans = fields.Function(
        fields.Many2Many('commission.commission_plan', None, None,
            'Top Level Commission Plans'),
        'get_parent_com_plans_id')
    brokers = fields.Many2Many('distribution.dist_network-broker',
        'dist_network', 'broker', 'Brokers',
        domain=[('is_broker', '=', True)])

    def get_parent_com_plans_id(self, name):
        parents = self.__class__.search([
                ('left', '<', self.left), ('right', '>', self.right),
                ('commission_plans', '>', 0),
                ])
        res = []
        for x in parents:
            res.extend(x.commission_plans)
        return [x.id for x in res]

class DistributionNetworkComPlanRelation(model.CoopSQL):
    'Relation Distribution Network - Commission Plan'

    __name__ = 'distribution.dist_network-plan'

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network', ondelete='CASCADE')
    com_plan = fields.Many2One('commission.commission_plan', 'Commission Plan',
        ondelete='RESTRICT')


class DistributionNetworkBrokerRelation(model.CoopSQL, model.CoopView):
    'Relation Distribution Network - Broker'

    __name__ = 'distribution.dist_network-broker'

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network', ondelete='RESTRICT')
    broker = fields.Many2One('party.party', 'Broker', ondelete='CASCADE')

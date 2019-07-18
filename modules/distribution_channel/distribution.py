# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import model, fields

__all__ = [
    'DistributionNetwork',
    'DistributionChannel',
    'DistributionNetworkChannelRelation',
    'CommercialProduct',
    'CommercialProductChannelRelation',
    ]


class DistributionNetwork(metaclass=PoolMeta):
    'Distribution Network'

    __name__ = 'distribution.network'

    authorized_distribution_channels = fields.Many2Many(
        'distribution.network-distribution.channel', 'distribution_network',
        'distribution_channel', 'Authorized Distribution Channels')
    parent_authorized_distribution_channels = fields.Function(
        fields.Many2Many('distribution.channel', None, None,
            'Top Level Distribution Channels'),
            'get_parent_distribution_channels_id')
    all_net_channels = fields.Function(
        fields.Many2Many('distribution.channel', None, None,
            'All network channels'), 'get_all_network_channels_id')

    @classmethod
    def __setup__(cls):
        super(DistributionNetwork, cls).__setup__()
        cls._error_messages.update({
            'net_must_have_at_least_one_channel':
                'at least one channel is required on %s network '
                'or its parents'})

    @classmethod
    def validate(cls, dis_networks):
        for network in dis_networks:
            if network.is_distributor:
                if not network.authorized_distribution_channels \
                        and not network.parent_authorized_distribution_channels:
                    cls.raise_user_error('net_must_have_at_least_one_channel',
                        network.get_rec_name(''))

    def get_parent_distribution_channels_id(self, name):
        return list({channel.id for parent in self.parents
            for channel in parent.authorized_distribution_channels})

    def get_all_network_channels_id(self, name):
        return list({x.id for x in
                self.authorized_distribution_channels +
                self.parent_authorized_distribution_channels})


class DistributionChannel(model.CodedMixin, model.CoogView):
    'Distribution Chanel'

    __name__ = 'distribution.channel'


class DistributionNetworkChannelRelation(model.CoogSQL):
    'Distribution Network Chanel Relation'

    __name__ = 'distribution.network-distribution.channel'

    distribution_network = fields.Many2One('distribution.network',
        'Distribution Network', required=True, ondelete='CASCADE')
    distribution_channel = fields.Many2One('distribution.channel',
        'Distribution Channel', required=True, ondelete='RESTRICT')


class CommercialProduct(metaclass=PoolMeta):
    'Commercial Product'

    __name__ = 'distribution.commercial_product'

    dist_authorized_channels = fields.Many2Many(
        'distribution.commercial_product-distribution.channel',
        'com_product', 'dist_channel', 'Authorized Distribution Channels')


class CommercialProductChannelRelation(model.CoogSQL):

    'Commercial Product Channel Relation'

    __name__ = 'distribution.commercial_product-distribution.channel'

    com_product = fields.Many2One('distribution.commercial_product',
        'Commercial Product', ondelete='CASCADE')
    dist_channel = fields.Many2One('distribution.channel',
        'Distribution Channel', ondelete='RESTRICT')

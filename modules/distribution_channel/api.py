# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import api_context
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA

__all__ = [
    'APIIdentity',
    'APICore',
    'APIContract',
    ]


class APIIdentity(metaclass=PoolMeta):
    __name__ = 'ir.api.identity'

    def get_api_context(self):
        context = super().get_api_context()
        if (self.user and self.user.dist_network and
                self.user.dist_network.all_net_channels):
            context['distribution_channels'] = [
                {
                    'id': channel.id,
                    'code': channel.code,
                    'name': channel.name,
                } for channel in self.user.dist_network.all_net_channels]
        return context


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _identity_context_output_schema(cls):
        schema = super()._identity_context_output_schema()
        schema['properties']['distribution_channels'] = {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'id': OBJECT_ID_SCHEMA,
                    'code': {'type': 'string'},
                    'name': {'type': 'string'},
                    },
                'required': ['id', 'code', 'name'],
                },
            }
        return schema

    @classmethod
    def _get_dist_channel(cls):
        pool = Pool()
        DistributionChannel = pool.get('distribution.channel')

        context = api_context()

        network = cls._get_dist_network()
        if ('distribution_channel' in context and
                context['distribution_channel']):
            channel = DistributionChannel(context['distribution_channel'])
            if channel.code == 'channel_3':
                pass
            if network and channel not in network.all_net_channels:
                pool.get('api').add_input_error({
                        'type': 'unauthorized_channel',
                        'data': {
                            'channel': channel.code,
                            'network': network.id,
                            },
                        })
            else:
                return channel

        if network is not None and len(network.all_net_channels) == 1:
            return network.all_net_channels[0]

        return None


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        # Commercial product is a function field, so we do nothing...
        contract.dist_channel = contract_data['dist_channel']

        return contract

    @classmethod
    def _contract_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')
        Core = pool.get('api.core')

        super()._contract_convert(data, options, parameters)
        channel = Core._get_dist_channel()

        if channel is None:
            API.add_input_error({
                    'type': 'missing_distribution_channel',
                    'data': {},
                    })
        else:
            data['dist_channel'] = channel

    @classmethod
    def _validate_contract_input(cls, data):
        pool = Pool()
        API = pool.get('api')

        super()._validate_contract_input(data)

        network = data['dist_network']
        channel = data['dist_channel']
        if channel.id not in [x.id for x in network.all_net_channels]:
            API.add_input_error({
                    'type': 'invalid_channel',
                    'data': {
                        'network': network.id,
                        'channel': channel.code,
                        'allowed_channels': sorted(
                            x.code for x in network.all_net_channels),
                        },
                    })

        if (data['commercial_product'].dist_authorized_channels and channel
                not in data['commercial_product'].dist_authorized_channels):
            API.add_input_error({
                    'type': 'unauthorized_channel_for_product',
                    'data': {
                        'channel': channel.code,
                        'product': data['commercial_product'].code,
                        },
                    })

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from trytond.pool import PoolMeta, Pool


__all__ = [
    'APICore',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _distribution_network_schema(cls):
        schema = super()._distribution_network_schema()
        schema['properties']['orias'] = {'type': 'string'}
        return schema

    @classmethod
    def _create_distribution_network(cls, network_data):
        network = super()._create_distribution_network(network_data)

        if 'orias' in network_data:
            # Ideally, we should update the parameters with the party
            # modification, but this becomes rather complicated for nothing. So
            # we will add the identifier right now
            network.party.update_identifier('orias', network_data['orias'])
            network.party.save()
        return network

    @classmethod
    def _distribution_network_convert(cls, data, parameters):
        API = Pool().get('api')

        super()._distribution_network_convert(data, parameters)
        if 'orias' in data and not data['party']:
            API.add_input_error({
                    'type': 'party_required_for_orias',
                    'data': {
                        'orias': data['orias'],
                        },
                    })

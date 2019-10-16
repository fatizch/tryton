# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import api_context
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, OBJECT_ID_SCHEMA
from trytond.modules.web_configuration.resource import WebUIResourceMixin
from trytond.modules.party_cog.api import PARTY_RELATION_SCHEMA

__all__ = [
    'APIIdentity',
    'APIIdentityWebResources',
    'APICore',
    'DistributionNetwork',
    ]


class APIIdentity(metaclass=PoolMeta):
    __name__ = 'ir.api.identity'

    def get_api_context(self):
        context = super().get_api_context()
        if self.user and self.user.dist_network:
            context['dist_network'] = self.user.dist_network.id
        return context


class APIIdentityWebResources(metaclass=PoolMeta):
    __name__ = 'ir.api.identity'

    def get_api_context(self):
        context = super().get_api_context()
        if self.user and self.user.dist_network:
            for parent in self.user.dist_network.parents:
                try:
                    context['theme'] = parent.get_web_resource_by_key('theme')
                    return context
                except KeyError:
                    pass
        return context


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'create_distribution_networks': {
                    'public': False,
                    'readonly': False,
                    'description': 'Creates a new node in the distribution '
                    'network tree',
                    },
                })

    @classmethod
    def _get_dist_network(cls):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        User = pool.get('res.user')

        network = None
        context = api_context()
        if 'dist_network' in context and context['dist_network']:
            network = DistNetwork(context['dist_network'])
        elif 'user' in context and context['user']:
            user = User(context['user'])
            if user.dist_network:
                network = user.dist_network
        return network

    @classmethod
    def create_distribution_networks(cls, parameters):
        pool = Pool()
        APIParty = pool.get('api.party')
        Network = pool.get('distribution.network')

        options = {}
        created = {}
        if 'parties' in parameters:
            APIParty._create_parties(parameters, created, options)

        networks = []
        for network in parameters['networks']:
            cls._create_distribution_network_update_parameters(network, created)
            networks.append(cls._create_distribution_network(network))

        Network.save(networks)
        created['networks'] = {}
        for network, data in zip(networks, parameters['networks']):
            created['networks'][data['ref']] = network

        return cls._create_distribution_networks_result(created)

    @classmethod
    def _create_distribution_network_update_parameters(cls, network_data,
            created):
        if (isinstance(network_data['party'], dict) and
                    'ref' in network_data['party']):
            network_data['party'] = created['parties'][
                network_data['party']['ref']]

    @classmethod
    def _create_distribution_network(cls, network_data):
        pool = Pool()
        Network = pool.get('distribution.network')

        network = Network()

        network.party = network_data['party']
        if 'name' in network_data:
            network.name = network_data['name']
        else:
            # Schema will ensure at least one of both is set
            network.name = network.party.name
        network.parent = network_data['parent']
        if 'code' in network_data:
            network.code = network_data['code']
        else:
            network.code = cls._generate_distribution_network_code(network_data)
        return network

    @classmethod
    def _generate_distribution_network_code(cls, network_data):
        # Try to generate a unique code based on the parent's code
        Network = Pool().get('distribution.network')
        cur_max_child = Network.search(
            [('parent', '=', network_data['parent'].id)],
            order=[('id', 'DESC')], limit=1)

        child_suffix = 0
        if cur_max_child:
            try:
                _, max_child_code = cur_max_child[0].code.rsplit('_', 1)
                child_suffix = int(max_child_code)
            except ValueError:
                pass
        child_suffix += 1
        while True:
            code_check = '%s_%i' % (network_data['parent'].code, child_suffix)
            if not Network.search([('code', '=', code_check)]):
                break
            child_suffix += 1
        return code_check

    @classmethod
    def _create_distribution_networks_result(cls, created):
        result = Pool().get('api.party')._create_parties_result(created)

        result['networks'] = []
        for ref, instance in created['networks'].items():
            result['networks'].append(
                {'ref': ref, 'id': instance.id, 'code': instance.code},
                )
        return result

    @classmethod
    def _create_distribution_networks_convert_input(cls, parameters):
        pool = Pool()
        PartyAPI = pool.get('api.party')

        options = {}

        parameters['parties'] = parameters.get('parties', [])
        for party in parameters['parties']:
            PartyAPI._party_convert(party, options, parameters)
        for network in parameters['networks']:
            cls._distribution_network_convert(network, parameters)
        return parameters

    @classmethod
    def _distribution_network_convert(cls, data, parameters):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        user_network = cls._get_dist_network()

        if not user_network and 'parent' not in data:
            API.add_input_error({
                    'type': 'missing_parent_network',
                    'data': {
                        'field': 'networks.parent',
                        },
                    })

        if 'parent' not in data:
            data['parent'] = user_network
        else:
            data['parent'] = API.instantiate_code_object(
                'distribution.network', data['parent'])

        if 'party' in data:
            subscriber = PartyAPI._party_from_reference(data['party'],
                parties=parameters['parties'])
            if subscriber:
                data['party'] = subscriber
        else:
            data['party'] = None

    @classmethod
    def _create_distribution_networks_validate_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')

        user_network = cls._get_dist_network()

        if not user_network:
            return

        for network_data in parameters['networks']:
            # Make sure the specified parent exists and is a sub node of the
            # user's network
            if network_data['parent'].id not in [
                    x.id for x in user_network.all_children]:
                API.add_input_error({
                        'type': 'unauthorized_network',
                        'data': {
                            'user_network': user_network.code,
                            'network': network_data['parent'].code,
                            },
                        })

    @classmethod
    def _create_distribution_networks_schema(cls):
        pool = Pool()
        PartyAPI = pool.get('api.party')
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'parties': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': PartyAPI._party_schema(),
                    },
                'networks': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._distribution_network_schema(),
                    'minItems': 1,
                    },
                },
            'required': ['networks'],
            }

    @classmethod
    def _distribution_network_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
                'party': PARTY_RELATION_SCHEMA,
                'name': {'type': 'string'},
                'parent': CODED_OBJECT_SCHEMA,
                'code': {'type': 'string'},
                },
            'required': ['ref'],
            'anyOf': [
                {'required': ['name']},
                {'required': ['party']},
                ],
            }

    @classmethod
    def _create_distribution_networks_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'required': ['networks'],
            'properties': {
                'parties': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'ref': {'type': 'string'},
                            'id': OBJECT_ID_SCHEMA,
                            },
                        'required': ['ref', 'id'],
                        },
                    },
                'networks': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'ref': {'type': 'string'},
                            'id': OBJECT_ID_SCHEMA,
                            'code': {'type': 'string'},
                            },
                        'required': ['ref', 'id', 'code'],
                        },
                    },
                },
            }

    @classmethod
    def _create_distribution_networks_examples(cls):
        return [
            {
                'input': {
                    'parties': [
                        {
                            'ref': '1',
                            'is_person': False,
                            'name': 'My Network',
                            },
                        ],
                    'networks': [
                        {
                            'ref': '1',
                            'party': {'ref': '1'},
                            'name': 'My Network Node',
                            'parent': {'code': 'C1010'},
                            },
                        ],
                    },
                'output': {
                    'parties': [
                        {
                            'ref': '1',
                            'id': 1,
                            }
                        ],
                    'networks': [
                        {
                            'ref': '1',
                            'id': 1,
                            'code': 'C10101',
                            },
                        ],
                    },
                },
            ]

    @classmethod
    def _identity_context_output_schema(cls):
        schema = super()._identity_context_output_schema()
        schema['properties']['dist_network'] = {'type': 'integer'}
        return schema


class DistributionNetwork(WebUIResourceMixin):
    __name__ = 'distribution.network'

    def _get_structure(self):
        res = super()._get_structure()
        if self.web_ui_resources:
            res['custom_resources'] = {
                x.key: x.value
                for x in self.web_ui_resources
                }
        return res

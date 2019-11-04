# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__name__ = [
    'APIProduct',
    'APIParty',
    'APIContract',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)

        # Maybe some day there will be some sort of "ssn_required" on item
        # descs
        if product.is_health and result['item_descriptors']:
            for item_desc in result['item_descriptors']:
                item_desc['fields']['required'].append('ssn')
                item_desc['fields']['fields'].append('ssn')

        return result


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _party_person_schema(cls):
        schema = super()._party_person_schema()
        schema['properties']['birth_order'] = {'type': 'number'}
        return schema

    @classmethod
    def _update_person(cls, party, data, options):
        super()._update_person(party, data, options)
        cls._update_party_complement(party, data, options)

    @classmethod
    def _update_party_complement(cls, party, data, options):
        complements = getattr(party, 'health_complement', [])
        if not complements:
            party.health_complement = [{}]
        else:
            party.health_complement = list(party.health_complement)


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _check_contract_parameters_covereds(cls, data, contract_data):
        API = Pool().get('api')

        super()._check_contract_parameters_covereds(data, contract_data)

        # Maybe some day there will be some sort of "ssn_required" on item
        # descs
        if contract_data['product'].is_health:
            party = data.get('party', None)
            if not party or not party.ssn:
                API.add_input_error({
                        'type': 'missing_ssn',
                        'data': {
                            'field': 'covered.party',
                            },
                        })

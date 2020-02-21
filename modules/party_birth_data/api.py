# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA


__all__ = [
    'APIProduct',
    'APIParty',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _update_covered_party_domains_from_item_desc(cls, item_desc, domains):
        super()._update_covered_party_domains_from_item_desc(item_desc, domains)
        if item_desc.kind == 'person' and item_desc.birth_zip_required:
            domains['subscription']['person_domain']['fields'].append(
                {'code': 'birth_zip_and_city', 'required': True})


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _party_person_schema(cls):
        party_schema = super()._party_person_schema()
        party_schema['properties']['birth_zip'] = {'type': 'string'}
        party_schema['properties']['birth_city'] = {'type': 'string'}
        party_schema['properties']['birth_country'] = CODED_OBJECT_SCHEMA
        return party_schema

    @classmethod
    def _party_convert(cls, data, options, parameters):
        API = Pool().get('api')
        super()._party_convert(data, options, parameters)
        if 'birth_country' in data:
            if 'code' in data['birth_country']:
                data['birth_country']['code'] = \
                    data['birth_country']['code'].upper()
            data['birth_country'] = API.instantiate_code_object(
                'country.country', data['birth_country'])

    @classmethod
    def _init_new_party(cls, data, options):
        party = super()._init_new_party(data, options)
        party.birth_city = data.get('birth_city', None)
        party.birth_zip = data.get('birth_zip', None)
        party.birth_country = data.get('birth_country', None)
        return party

    @classmethod
    def _update_party(cls, party, data, options):
        super()._update_party(party, data, options)
        birth_city = data.get('birth_city', None)
        if birth_city != party.birth_city:
            party.birth_city = birth_city
        birth_zip = data.get('birth_zip', None)
        if birth_zip != party.birth_zip:
            party.birth_zip = birth_zip
        birth_country = data.get('birth_country', None)
        if birth_country != party.birth_country:
            party.birth_country = birth_country

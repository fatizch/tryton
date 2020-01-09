# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__name__ = [
    'APIParty',
    'APIContract',
    ]


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

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model.multivalue import filter_pattern


__all__ = [
    'Configuration',
    ]


class Configuration(metaclass=PoolMeta):
    __name__ = 'party.configuration'

    @classmethod
    def default_party_sequence(cls, **pattern):
        Sequence = Pool().get('ir.sequence')
        pattern = filter_pattern(pattern, Sequence)
        domain = [('code', '=', 'party.party')]
        for key, value in pattern.items():
            domain.append((str(key), '=', value))
        sequences = Pool().get('ir.sequence').search(domain)
        if len(sequences) == 1:
            return sequences[0].id

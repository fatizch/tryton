# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'ConfigurationSequence',
    'Configuration',
    ]


class ConfigurationSequence:
    __metaclass__ = PoolMeta
    __name__ = 'party.configuration.party_sequence'

    @classmethod
    def default_party_sequence(cls):
        sequences = Pool().get('ir.sequence').search(
            [('code', '=', 'party.party')])
        if len(sequences) == 1:
            return sequences[0].id


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'party.configuration'

    @classmethod
    def default_party_sequence(cls):
        return cls.multivalue_model('party_sequence').default_party_sequence()

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'Configuration',
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'party.configuration'

    @classmethod
    def default_party_sequence(cls, **pattern):
        domain = [('code', '=', 'party.party')]
        if pattern:
            for key, value in pattern['pattern'].iteritems():
                domain.append((str(key), '=', value))
        sequences = Pool().get('ir.sequence').search(domain)
        if len(sequences) == 1:
            return sequences[0].id

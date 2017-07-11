# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Party',
    'Address',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    @classmethod
    def copy(cls, parties, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('sepa_mandates', None)
        return super(Party, cls).copy(parties, default=default)

    @classmethod
    def _export_light(cls):
        return super(Party, cls)._export_light() | {'sepa_mandates'}


class Address:
    __metaclass__ = PoolMeta
    __name__ = 'party.address'

    def street_for_sepa(self):
        return self.one_line_street

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unicodedata

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

    @property
    def sepa_adrline_1(self):
        return unicodedata.normalize('NFKD', ' '.join(
                [x.strip() for x in self.street.splitlines() if x.strip()]
                )).encode('ascii', 'replace')[:70]

    @property
    def sepa_adrline_2(self):
        return unicodedata.normalize('NFKD', ' '.join(
                [self.zip, self.city])).encode('ascii', 'replace')[:70]

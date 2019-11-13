# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _update_covered_party_domains_from_item_desc(cls, item_desc, domains):
        super()._update_covered_party_domains_from_item_desc(item_desc, domains)
        if item_desc.kind == 'person' and item_desc.birth_zip_required:
            domains['subscription']['person_domain']['fields'].append(
                {'code': 'birth_zip_and_city', 'required': True})

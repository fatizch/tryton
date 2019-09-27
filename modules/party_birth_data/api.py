# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_item_descriptor_fields(cls, item_desc):
        description = super()._describe_item_descriptor_fields(item_desc)
        if item_desc.kind == 'person' and item_desc.birth_zip_required:
            description['required'].append('birth_zip_and_city')
            description['fields'].append('birth_zip_and_city')
        return description

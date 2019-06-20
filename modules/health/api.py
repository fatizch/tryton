# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__name__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)

        if product.is_health:
            APICore = Pool().get('api.core')

            # Could be more pinpoint (information is per coverage), but this is
            # not important for now
            for descriptor in result['item_descriptors'].values():
                descriptor['fields']['ssn'] = APICore._field_description(
                    'party.party', 'ssn', required=True, sequence=100)
        return result

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
                descriptor['fields']['healthcare_system'] = \
                    APICore._field_description(
                        'health.party_complement', 'hc_system', required=True,
                        sequence=110)
                descriptor['fields']['healthcare_system']['type'] = 'string'
                descriptor['fields']['insurance_fund'] = \
                    APICore._field_description(
                        'health.party_complement', 'insurance_fund',
                        required=True, sequence=120)
                descriptor['fields']['insurance_fund']['type'] = 'string'
        return result

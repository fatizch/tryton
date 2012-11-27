#-*- coding:utf-8 -*

from trytond.pool import PoolMeta
from trytond.model import fields

from trytond.modules.life_product import LifeCoverage
__all__ = [
    'GroupLifeCoverage',
    'GroupPricingData',
]


class GroupLifeCoverage(LifeCoverage):
    'Coverage'

    __name__ = 'ins_collective.coverage'


class GroupPricingData():
    'Pricing Data'

    __name__ = 'ins_collective.pricing_data'
    __metaclass__ = PoolMeta

    tranche_calculator = fields.One2Many('tranche.calculator',
        'pricing_data', 'Tranche Calculator', size=1)

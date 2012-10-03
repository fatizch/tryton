#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta

from trytond.modules.insurance_product import ProductDefinition

__all__ = ['LifeCoverage', 'LifeProductDefinition']


class LifeCoverage():
    'Life Coverage'

    __metaclass__ = PoolMeta

    __name__ = 'ins_product.coverage'

    @classmethod
    def __setup__(cls):
        super(LifeCoverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        if not ('life_product.definition', 'Life') in cls.family.selection:
            cls.family.selection.append(
                ('life_product.definition', 'Life'))
        if ('default', 'default') in cls.family.selection:
            cls.family.selection.append(
                ('default', 'default'))


class LifeProductDefinition(ProductDefinition):
    'Life Product Definition'

    __name__ = 'life_product.definition'

    @staticmethod
    def get_extension_model():
        return 'extension_life'

    @staticmethod
    def get_step_model(step_name):
        steps = {
            'extension': 'life_contract.extension_life_state',
            }
        return steps[step_name]

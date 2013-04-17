#-*- coding:utf-8 -*-
import copy

from trytond.modules.coop_utils import CoopSQL, utils
from trytond.modules.insurance_product import Offered

__all__ = ['HealthCoverage']


class HealthCoverage(CoopSQL, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'

    @classmethod
    def __setup__(cls):
        super(HealthCoverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        utils.append_inexisting(cls.family.selection,
            ('health', 'Health'))
        if ('default', 'default') in cls.family.selection:
            cls.family.selection.remove(('default', 'default'))

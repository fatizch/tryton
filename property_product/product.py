#-*- coding:utf-8 -*-
import copy

from trytond.modules.coop_utils import CoopSQL
from trytond.modules.insurance_product import Offered

__all__ = ['Coverage']


class Coverage(CoopSQL, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        if not ('pc', 'Property & Casualty') in cls.family.selection:
            cls.family.selection.append(('pc', 'Property & Casualty'))

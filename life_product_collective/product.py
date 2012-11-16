#-*- coding:utf-8 -*-

from trytond.modules.life_product import LifeCoverage
__all__ = ['GroupLifeCoverage']


class GroupLifeCoverage(LifeCoverage):
    'Coverage'

    __name__ = 'ins_collective.coverage'

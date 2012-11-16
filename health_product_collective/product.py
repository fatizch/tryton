#-*- coding:utf-8 -*-

from trytond.modules.health_product import HealthCoverage
__all__ = ['GroupHealthCoverage']


class GroupHealthCoverage(HealthCoverage):
    'Coverage'

    __name__ = 'ins_collective.coverage'

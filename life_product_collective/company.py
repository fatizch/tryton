#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__all__ = [
    'Employee',
]


class Employee():
    'Employee'
    __name__ = 'party.employee'
    __metaclass__ = PoolMeta

    college = fields.Many2One('party.college', 'College', required=True)

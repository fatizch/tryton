#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = [
'Employee',
]


class Employee():
    'Employee'
    __name__ = 'party.employee'
    __metaclass__ = PoolMeta

    college = fields.Many2One('party.college', 'College', required=True)

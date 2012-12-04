#-*- coding:utf-8 -*-

from trytond.model import fields
from trytond.modules.coop_utils import CoopSQL, CoopView

__all__ = [
    'College',
    'CollegeTranche',
]


class College(CoopSQL, CoopView):
    'College'

    __name__ = 'party.college'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name')
    tranches = fields.Many2Many('party.college_tranche', 'college', 'tranche',
        'Tranches')


class CollegeTranche(CoopSQL):
    ' '

    __name__ = 'party.college_tranche'

    college = fields.Many2One('party.college', 'College',
        ondelete='CASCADE')
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        ondelete='RESTRICT')

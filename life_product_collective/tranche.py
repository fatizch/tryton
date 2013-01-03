#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.coop_utils import utils


PAYER_KIND = [
    ('employer', 'Employer'),
    ('employee', 'Employee'),
    ('beneficiary', 'Beneficiary')
]

__all__ = [
    'TrancheCalculator',
    'TrancheCalculatorLine',
]


class TrancheCalculator():
    'Tranche Calculator'

    __name__ = 'tranche.calculator'
    __metaclass__ = PoolMeta

    pricing_component = fields.Many2One('ins_collective.pricing_component',
        'Pricing Data', ondelete='CASCADE')


class TrancheCalculatorLine():
    'Tranche Calculator Line'

    __name__ = 'tranche.calc_line'
    __metaclass__ = PoolMeta

    payer_kind = fields.Selection(PAYER_KIND, 'At The Expense Of')

#    @classmethod
#    def __setup__(cls):
#        super(TrancheCalculatorLine, cls).__setup__()
#        cls.tranche = copy.copy(cls.tranche)
#        if not cls.tranche.domain:
#            cls.tranche.domain = []
#        cur_domain = ('id', 'in',
#            Eval('_parent._parent._parent.college.tranches'))
#        utils.append_inexisting(cls.tranche.domain, cur_domain)

    @staticmethod
    def default_payer_kind():
        return 'employer'

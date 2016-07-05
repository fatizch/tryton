# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'ClaimService',
    ]


class ClaimService:
    __name__ = 'claim.service'

    is_loan = fields.Function(
        fields.Boolean('Is loan', states={'invisible': True}),
        'get_is_loan')
    loan = fields.Many2One('loan', 'Loan', ondelete='RESTRICT',
        domain=[('contracts', '=', Eval('contract'))],
        states={'invisible': ~Eval('is_loan')},
        depends=['contract', 'is_loan'])

    @classmethod
    def _export_light(cls):
        return super(ClaimService, cls)._export_light() | {'loan'}

    def get_loan(self):
        return self.loan

    def get_is_loan(self, name):
        return self.option.is_loan

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(
            cur_dict)
        if self.loss.loss_desc.loss_kind == 'life':
            if not self.is_loan:
                return
            cur_dict['loan'] = self.loan
            if self.loan:
                cur_dict['payment'] = self.loan.get_payment(cur_dict['date'])
                cur_dict['share'] = self.loan.get_loan_share(
                    self.loss.covered_person, cur_dict['date'])

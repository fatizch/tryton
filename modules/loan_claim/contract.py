from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'ContractService',
    ]


class ContractService:
    __name__ = 'contract.service'

    is_loan = fields.Function(
        fields.Boolean('Is loan', states={'invisible': True}),
        'get_is_loan')
    loan = fields.Many2One('loan', 'Loan',
        domain=[('contract', '=', Eval('contract'))],
        states={'invisible': ~Eval('is_loan')},
        depends=['contract', 'is_loan'])

    def get_loan(self):
        return self.loan

    def get_is_loan(self, name):
        return self.subscribed_service.is_loan

    def init_dict_for_rule_engine(self, cur_dict):
        super(ContractService, self).init_dict_for_rule_engine(
            cur_dict)
        if not self.is_loan:
            return
        cur_dict['loan'] = self.loan
        cur_dict['share'] = self.loan.get_loan_share(self.loss.covered_person)

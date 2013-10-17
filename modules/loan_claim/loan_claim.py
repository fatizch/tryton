from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields

__all__ = [
    'LoanClaimDeliveredService',
    'LoanIndemnification',
    ]


class LoanClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    is_loan = fields.Function(
        fields.Boolean('Is loan', states={'invisible': True}),
        'get_is_loan')
    loan = fields.Many2One('loan.loan', 'Loan',
        domain=[('contract', '=', Eval('contract'))],
        states={'invisible': ~Eval('is_loan')},
        depends=['contract', 'is_loan'])

    def get_loan(self):
        return self.loan

    def get_is_loan(self, name):
        return self.subscribed_service.is_loan

    def init_dict_for_rule_engine(self, cur_dict):
        super(LoanClaimDeliveredService, self).init_dict_for_rule_engine(
            cur_dict)
        if not self.is_loan:
            return
        cur_dict['loan'] = self.loan
        cur_dict['share'] = self.loan.get_loan_share(self.loss.covered_person)


class LoanIndemnification():
    'Indemnification'

    __name__ = 'claim.indemnification'
    __metaclass__ = PoolMeta

    def init_from_delivered_service(self, delivered_service):
        super(LoanIndemnification, self).init_from_delivered_service(
            delivered_service)
        if not delivered_service.is_loan:
            return
        self.beneficiary = delivered_service.loan.lender.party

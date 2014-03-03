from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'ContractClause',
    ]


class ContractClause:
    __name__ = 'contract.clause'

    loan_share = fields.Many2One('loan.share', 'Loan Share', domain=[
            ('id', 'in', Eval('_parent_covered_data', {}).get(
                    'loan_shares', []))],
        states={'invisible': ~Eval('is_loan')})
    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')

    def get_is_loan(self, name):
        if self.covered_data:
            return self.covered_data.is_loan
        if self.contract:
            return self.contract.is_loan

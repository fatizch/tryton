from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta

__all__ = [
    'ContractClause',
    'CoveredData',
    'Contract',
    ]


class ContractClause:
    __name__ = 'contract.clause'

    loan_share = fields.Many2One('loan.share', 'Loan Share', domain=[
            ('id', 'in', Eval('_parent_covered_data', {}).get(
                    'loan_shares', []))],
        states={'invisible': ~Eval('is_loan')}, ondelete='CASCADE')
    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'on_change_with_is_loan')

    @fields.depends('covered_data', 'contract')
    def on_change_with_is_loan(self, name=None):
        if self.covered_data:
            return self.covered_data.is_loan
        if self.contract:
            return self.contract.is_loan


class CoveredData:
    __name__ = 'contract.covered_data'

    def check_loan_beneficiary_clauses(self):
        if not self.option.offered.clause_rules:
            return True, []
        good_rule = utils.find_date(self.option.offered.clause_rules,
            self.option.contract.appliable_conditions_date)
        if not good_rule.has_beneficiary_clauses:
            return True, []
        res, errs = True, []
        shares = set([x for x in self.loan_shares])
        clauses = set([x.loan_share for x in self.beneficiary_clauses])
        for elem in shares - clauses:
            res = False
            errs.append(('no_beneficiary_clause_for_loan', (elem.rec_name,)))
        return res, errs

    def check_beneficiary_clauses(self):
        res, errs = super(CoveredData, self).check_beneficiary_clauses()
        loan_res, loan_errs = self.check_loan_beneficiary_clauses()
        return res and loan_res, errs + loan_errs


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
                'no_beneficiary_clause_for_loan': 'No beneficiary clause '
                'selected for loan %s',
                })

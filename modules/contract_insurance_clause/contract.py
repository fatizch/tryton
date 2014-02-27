from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    'CoveredData',
    ]


class Contract:
    __name__ = 'contract'

    def init_clauses(self, offered):
        ContractClause = Pool().get('contract.clause')
        clauses, errs = offered.get_result('all_clauses', {
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date,
                })
        if errs or not clauses:
            return
        self.clauses = []
        for clause in clauses:
            new_clause = ContractClause()
            new_clause.clause = clause
            new_clause.text = clause.get_good_version_at_date(
                self.start_date).content
            self.clauses.append(new_clause)

    def init_from_offered(self, offered, start_date, end_date):
        result = super(Contract, self).init_from_offered(offered, start_date,
            end_date)
        self.init_clauses(offered)
        return result


class CoveredData:
    __name__ = 'contract.covered_data'

    clauses = fields.One2Many('contract.clause', 'covered_data',
        'Clauses', context={'start_date': Eval('start_date')})

    def init_clauses(self, option):
        clauses, errs = self.option.offered.get_result('all_clauses', {
                'date': option.start_date,
                'appliable_conditions_date':
                self.option.contract.appliable_conditions_date,
            })
        self.clauses = []
        if errs or not clauses:
            return
        ContractClause = Pool().get('contract.clause')
        for clause in clauses:
            new_clause = ContractClause()
            new_clause.clause = clause
            new_clause.text = clause.get_version_at_date(
                option.start_date).content
            new_clause.contract = option.contract
            self.clauses.append(new_clause)

    def init_from_option(self, option):
        super(CoveredData, self).init_from_option(option)
        self.init_clauses(option)

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __name__ = 'contract'

    clauses = fields.One2Many('contract.clause', 'contract', 'Clauses',
        context={'start_date': Eval('start_date')},
        domain=[('clause', 'in', Eval('possible_clauses'))],
        depends=['possible_clauses', 'start_date'])
    possible_clauses = fields.Function(
        fields.One2Many('clause', '', 'Possible clauses'),
        'on_change_with_possible_clauses')

    @fields.depends('product', 'appliable_conditions_date')
    def on_change_with_possible_clauses(self, name=None):
        if not self.product.clause_rules:
            return []
        good_rule = utils.find_date(self.product.clause_rules,
            self.appliable_conditions_date)
        return [elem.id for elem in good_rule.clauses]


class ContractOption:
    __name__ = 'contract.option'

    clauses = fields.One2Many('contract.clause', 'option', 'Clauses',
        domain=[('clause', 'in', Eval('possible_clauses'))],
        depends=['possible_clauses'])
    possible_clauses = fields.Function(
        fields.One2Many('clause', '', 'Possible clauses'),
        'on_change_with_possible_clauses')

    @fields.depends('coverage', 'appliable_conditions_date')
    def on_change_with_possible_clauses(self, name=None):
        if not self.coverage.clause_rules:
            return []
        good_rule = utils.find_date(self.coverage.clause_rules,
            self.appliable_conditions_date)
        return [elem.id for elem in good_rule.clauses]

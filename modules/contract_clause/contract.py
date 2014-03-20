from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    clauses = fields.One2Many('contract.clause', 'contract',
        'Clauses', context={'start_date': Eval('start_date')},
        domain=[('clause', 'in', Eval('possible_clauses'))],
        depends=['possible_clauses'])
    possible_clauses = fields.Function(
        fields.One2Many('clause', '', 'Possible clauses'),
        'on_change_with_possible_clauses')

    @fields.depends('option')
    def on_change_with_possible_clauses(self, name=None):
        if not self.offered.clause_rules:
            return []
        good_rule = utils.find_date(self.offered.clause_rules,
            self.appliable_conditions_date)
        return [elem.id for elem in good_rule.clauses]

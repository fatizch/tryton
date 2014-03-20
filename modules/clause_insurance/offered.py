from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields
from trytond.modules.offered import NonExistingRuleKindException

__metaclass__ = PoolMeta

__all__ = [
    'OfferedMixin',
    'Product',
    'OptionDescription',
    ]


class OfferedMixin:
    __name__ = 'offered'

    clause_rules = fields.One2Many('clause.rule', 'offered', 'Clause Rules')

    def give_me_all_clauses(self, args):
        try:
            return self.get_result('all_clauses', args, kind='clause')
        except NonExistingRuleKindException:
            return [], ()


class Product(OfferedMixin):
    __name__ = 'offered.product'


class OptionDescription(OfferedMixin):
    __name__ = 'offered.option.description'

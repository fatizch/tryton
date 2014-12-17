from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'CoveredElement',
    'ExtraPremium',
    'Premium',
    ]


class Contract:
    __name__ = 'contract'

    def appliable_fees(self):
        all_fees = super(Contract, self).appliable_fees()
        covered_element_option_fees = {fee
            for option in self.covered_element_options
            for fee in option.coverage.fees}
        return all_fees | covered_element_option_fees


class CoveredElement:
    __name__ = 'contract.covered_element'

    premiums = fields.One2Many('contract.premium', 'covered_element',
        'Premiums')

    @classmethod
    def functional_skips_for_duplicate(cls):
        return (super(CoveredElement, cls).functional_skips_for_duplicate() |
            set(['premiums']))


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    premiums = fields.One2Many('contract.premium', 'extra_premium',
        'Premiums')


class Premium:
    __name__ = 'contract.premium'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', select=True, ondelete='CASCADE')
    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium', select=True, ondelete='CASCADE')

    def get_main_contract(self, name=None):
        if self.covered_element:
            return self.covered_element.main_contract.id
        elif self.extra_premium:
            return self.extra_premium.option.parent_contract.id
        return super(Premium, self).get_main_contract(name)

    @classmethod
    def get_possible_parent_field(cls):
        return super(Premium, cls).get_possible_parent_field() | {
            'covered_element', 'extra_premium'}

    @classmethod
    def search_main_contract(cls, name, clause):
        new_clause = super(Premium, cls).search_main_contract(name, clause)
        new_clause += [
            ('covered_element.contract',) + tuple(clause[1:]),
            ('extra_premium.option.parent_contract',) + tuple(clause[1:]),
            ]
        return new_clause

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.coog_core import fields

# Keys should exist in premium.offered.PREMIUM_FREQUENCY
EXTRA_PREMIUM_FREQUENCIES = [
    ('', ''),
    ('yearly', 'Per Year'),
    ]

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
        'Premiums', delete_missing=True, target_not_required=True,
        readonly=True)

    @classmethod
    def functional_skips_for_duplicate(cls):
        return (super(CoveredElement, cls).functional_skips_for_duplicate() |
            set(['premiums']))


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    flat_amount_frequency = fields.Selection(EXTRA_PREMIUM_FREQUENCIES,
        'Amount frequency', states={
            'invisible': Eval('calculation_kind', '') != 'flat',
            'required': Eval('calculation_kind', '') == 'flat'},
            depends=['calculation_kind'],
            domain=[If(Eval('calculation_kind') == 'rate',
                ('flat_amount_frequency', '=', ''),
                ('flat_amount_frequency', '!=', ''))])
    premiums = fields.One2Many('contract.premium', 'extra_premium',
        'Premiums', delete_missing=True, target_not_required=True,
        readonly=True)

    @fields.depends('calculation_kind')
    def on_change_with_flat_amount_frequency(self):
        return '' if self.calculation_kind == 'rate' else 'yearly'


class Premium:
    __name__ = 'contract.premium'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', select=True, ondelete='CASCADE', readonly=True)
    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium', select=True, ondelete='CASCADE', readonly=True)

    def _get_main_contract(self):
        if self.covered_element:
            return self.covered_element.main_contract.id
        elif self.extra_premium:
            return self.extra_premium.option.parent_contract.id
        return super(Premium, self)._get_main_contract()

    @classmethod
    def get_possible_parent_field(cls):
        return super(Premium, cls).get_possible_parent_field() | {
            'covered_element', 'extra_premium'}

    @classmethod
    def get_premium_tree(cls, contracts):
        data_dict = super(Premium, cls).get_premium_tree(contracts)
        data_dict.update({
                'covered_element': [],
                'extra_premium': [],
                })
        for contract in contracts:
            for covered_element in contract.covered_elements:
                data_dict['covered_element'].append(covered_element.id)
                for option in covered_element.options:
                    data_dict['option'].append(option.id)
                    data_dict['extra_premium'] += [x.id
                        for x in option.extra_premiums]
            for option in contract.options:
                data_dict['extra_premium'] += [x.id
                    for x in option.extra_premiums]
        return data_dict

    @property
    def full_name(self):
        if self.option and self.option.covered_element:
            return ', '.join([self.rec_name,
                    self.option.covered_element.rec_name])
        return self.rec_name

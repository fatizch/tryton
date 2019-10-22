# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pyson import Eval
from trytond.modules.coog_core import model, fields

from .waiver import PremiumModificationMixin


class DiscountModification(
        PremiumModificationMixin, model.CoogSQL, model.CoogView):
    "Discount on Premiums"
    __name__ = 'contract.premium_modification.discount'

    options = fields.Many2Many(
        'contract.premium_modification.discount-contract.option',
        'discount', 'option', "Options", readonly=True)
    discount_options = fields.One2Many(
        'contract.premium_modification.discount-contract.option',
        'discount', "Discount Options", delete_missing=True, readonly=True)
    option_names = fields.Function(
        fields.Char("Option Names"), 'on_change_with_option_names')

    @property
    def premium_modification_options(self):
        return self.discount_options

    @premium_modification_options.setter
    def premium_modification_options(self, options):
        self.discount_options = options

    @fields.depends('options')
    def on_change_with_option_names(self, name=None):
        return ', '.join(
            '%s - %s' % (o.covered_element.party.full_name, o.coverage.name)
            for o in self.options)


class DiscountModificationOption(model.CoogSQL, model.CoogView):
    "Discount Option"
    __name__ = 'contract.premium_modification.discount-contract.option'

    option = fields.Many2One('contract.option', 'Option', required=True,
        ondelete='CASCADE', select=True, readonly=True)
    discount = fields.Many2One('contract.premium_modification.discount',
        "Discount", required=True, ondelete='CASCADE', select=True,
        readonly=True)
    discount_rule = fields.Many2One('commercial_discount.rule', "Discount Rule",
        required=True, ondelete='RESTRICT', readonly=True)
    start_date = fields.Date('Start Date', readonly=True)
    end_date = fields.Date('End Date', readonly=True,
        domain=['OR',
            ('end_date', '>=', Eval('start_date')),
            ('end_date', '=', None),
            ],
        depends=['start_date'])

    @property
    def premium_modification(self):
        return self.discount

    @property
    def modification_rule(self):
        return self.discount_rule

    @modification_rule.setter
    def modification_rule(self, rule):
        self.discount_rule = rule

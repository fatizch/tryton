#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields
from trytond.modules.insurance_product.business_rule import business_rule

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    'CommissionOptionDescriptionOptionDescriptionRelation',
    'CommissionRule',
    ]

COMMISSION_KIND = [
    ('', ''),
    ('business_provider', 'Business Provider'),
    ('management', 'Management Delegation'),
    ]


class Product:
    __name__ = 'offered.product'

    dist_networks = fields.Many2Many('distribution.network-commission.plan',
        'com_plan', 'dist_network', 'Distribution Networks')
    commission_kind = fields.Selection(COMMISSION_KIND, 'Commission Kind',
        states={
            'invisible': ~(Eval('kind') == 'commission'),
            'required': ~~(Eval('kind') == 'commission'),
            })

    @classmethod
    def get_possible_product_kind(cls):
        res = super(OptionDescription,
            cls).get_possible_product_kind()
        res.append(('commission', 'Commission'))
        return res

    @classmethod
    def _export_skips(cls):
        result = super(Product, cls)._export_skips()
        result.add('dist_networks')
        return result


class OptionDescription:
    __name__ = 'offered.option.description'

    commission_rules = fields.One2Many('commission.rule',
        'offered', 'Commission Rules')
    coverages = fields.Many2Many(
        'commission.option.description-option.description', 'component',
        'coverage', 'Coverages', domain=[('kind', '=', 'insurance')])

    @classmethod
    def get_possible_option_description_kind(cls):
        res = super(OptionDescription,
            cls).get_possible_option_description_kind()
        res.append(('commission', 'Commission'))
        return res

    def give_me_commission(self, args):
        return self.get_result(args=args, kind='commission')


class CommissionOptionDescriptionOptionDescriptionRelation(model.CoopSQL):
    'Commission Option Description-Option Description Relation'

    __name__ = 'commission.option.description-option.description'

    component = fields.Many2One('offered.option.description', 'Component',
        ondelete='CASCADE')
    coverage = fields.Many2One('offered.option.description',
        'Option Description', ondelete='RESTRICT')


class CommissionRule(business_rule.BusinessRuleRoot, model.CoopSQL):
    'Commission Rule'

    __name__ = 'commission.rule'

    rate = fields.Numeric('Rate', digits=(16, 4), states={
            'invisible': business_rule.STATE_ADVANCED,
            'required': ~business_rule.STATE_ADVANCED,
            })

    def get_simple_result(self, args):
        return self.rate

    def get_simple_rec_name(self):
        return '%s %%' % (self.rate * 100)

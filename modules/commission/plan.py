#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields
from trytond.modules.insurance_product.business_rule import business_rule

__all__ = [
    'CommissionPlan',
    'CommissionComponent',
    'CommissionComponentCoverageRelation',
    'CommissionRule',
    ]

COMMISSION_KIND = [
    ('', ''),
    ('business_provider', 'Business Provider'),
    ('management', 'Management Delegation'),
    ]


class CommissionPlan():
    'Commission Plan'

    __name__ = 'offered.product'
    __metaclass__ = PoolMeta

    dist_networks = fields.Many2Many('distribution.dist_network-plan',
        'com_plan', 'dist_network', 'Distribution Networks')
    commission_kind = fields.Selection(COMMISSION_KIND, 'Commission Kind',
        states={
            'invisible': ~(Eval('kind') == 'commission'),
            'required': ~~(Eval('kind') == 'commission')})

    @classmethod
    def __setup__(cls):
        super(CommissionPlan, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('commission', 'Commission'))
        if ('default', 'Default') in cls.kind.selection:
            cls.kind.selection.remove(('default', 'Default'))
        cls.kind.selection = list(set(cls.kind.selection))

    @classmethod
    def _export_skips(cls):
        result = super(CommissionPlan, cls)._export_skips()
        result.add('dist_networks')
        return result


class CommissionComponent():
    'Commission Component'

    __name__ = 'offered.coverage'
    __metaclass__ = PoolMeta

    commission_rules = fields.One2Many('commission.commission_rule',
        'offered', 'Commission Rules')
    coverages = fields.Many2Many('commission.component-coverage', 'component',
        'coverage', 'Coverages', domain=[('kind', '=', 'insurance')])

    @classmethod
    def __setup__(cls):
        super(CommissionComponent, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('commission', 'Commission'))
        if ('default', 'Default') in cls.kind.selection:
            cls.kind.selection.remove(('default', 'Default'))
        cls.kind.selection = list(set(cls.kind.selection))

    def give_me_commission(self, args):
        res, errs = self.get_result(args=args, kind='commission')
        if hasattr(res, 'result'):
            return res.result, errs
        return res, errs


class CommissionComponentCoverageRelation(model.CoopSQL):
    'Relation Commission Component and Coverage'

    __name__ = 'commission.component-coverage'

    component = fields.Many2One('offered.coverage', 'Component',
        ondelete='CASCADE')
    coverage = fields.Many2One('offered.coverage', 'Coverage',
        ondelete='RESTRICT')


class CommissionRule(business_rule.BusinessRuleRoot, model.CoopSQL):
    'Commission Rule'

    __name__ = 'commission.commission_rule'

    rate = fields.Numeric('Rate', states={
            'invisible': business_rule.STATE_ADVANCED,
            'required': ~business_rule.STATE_ADVANCED,
            })

    def get_simple_result(self, args):
        return self.rate

    def get_simple_rec_name(self):
        return '%s %%' % (self.rate * 100)

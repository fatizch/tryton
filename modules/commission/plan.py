#-*- coding:utf-8 -*-
import copy

from trytond.modules.coop_utils import model, fields
from trytond.modules.insurance_product import product
from trytond.modules.insurance_product.business_rule import business_rule

__all__ = [
    'CommissionPlan',
    'CommissionComponent',
    'CommissionPlanComponentRelation',
    'CommissionComponentCoverageRelation',
    'CommissionRule',
    ]


class CommissionPlan(model.CoopSQL, product.Offered):
    'Commission Plan'

    __name__ = 'commission.commission_plan'

    components = fields.Many2Many('commission.plan-component',
        'plan', 'component', 'Components')


class CommissionComponent(model.CoopSQL, product.Offered):
    'Commission Component'

    __name__ = 'commission.commission_component'

    commission_rules = fields.One2Many('commission.commission_rule',
        'offered', 'Commission Rules')
    coverages = fields.Many2Many('commission.component-coverage', 'component',
        'coverage', 'Coverages')


class CommissionPlanComponentRelation(model.CoopSQL):
    'Relation Commission Plan and Component'

    __name__ = 'commission.plan-component'

    plan = fields.Many2One('commission.commission_plan', 'Commission Plan',
        ondelete='CASCADE')
    component = fields.Many2One('commission.commission_component',
        'Commission Component', ondelete='RESTRICT')


class CommissionComponentCoverageRelation(model.CoopSQL):
    'Relation Commission Component and Coverage'

    __name__ = 'commission.component-coverage'

    component = fields.Many2One('commission.commission_component', 'Component',
        ondelete='CASCADE')
    coverage = fields.Many2One('ins_product.coverage', 'Coverage',
        ondelete='RESTRICT')


class CommissionRule(business_rule.BusinessRuleRoot, model.CoopSQL):
    'Commission Rule'

    __name__ = 'commission.commission_rule'

    rate = fields.Numeric('Rate', states={
            'invisible': business_rule.STATE_ADVANCED,
            'required': ~business_rule.STATE_ADVANCED,
            })

    def get_simple_result(self, args):
        return self.rate, []

    def get_simple_rec_name(self):
        return '%s %%' % self.rate

    @classmethod
    def __setup__(cls):
        cls.offered = copy.copy(cls.offered)
        cls.offered = fields.Many2One('commission.commission_component',
            'Offered')
        super(CommissionRule, cls).__setup__()

#-*- coding:utf-8 -*-
from trytond.pyson import Eval, And, Not, Or

from trytond.modules.coop_utils import model, utils, fields
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot

__all__ = [
    'TermRenewalRule',
]


class TermRenewalRule(BusinessRuleRoot, model.CoopSQL):
    'Term and Renewal Rule'

    __name__ = 'ins_product.term_renewal_rule'

    with_term = fields.Boolean('With Term')

    can_be_renewed = fields.Boolean(
        'Can be renewed',
        states={'invisible': ~Eval('with_term')})

    term_date_choice = fields.Selection([
            ('subscription', 'At subscription Time'),
            ('this_date', 'At this Date')],
        'Term Date Selection',
        states={'invisible': ~Eval('with_term')})

    date_for_sync = fields.Date(
        'Sync Date',
        states={
            'required': And(
                Eval('term_date_choice') == 'this_date',
                ~~Eval('with_term'),
                ~~Eval('can_be_renewed')),
            'invisible': Or(
                Eval('term_date_choice') != 'this_date',
                ~Eval('with_term'))})

    frequency = fields.Selection([
            ('biyearly', 'Biyearly'),
            ('yearly', 'Yearly'),
            ('half-yearly', 'Half Yearly'),
            ('quarterly', 'Quarterly'),
            ('monthly', 'Monthly')
        ],
        'Frequency',
        states={
            'invisible': Not(And(
                ~~Eval('with_term'),
                ~~Eval('can_be_renewed')))})

    @staticmethod
    def default_config_kind():
        return 'simple'

    @staticmethod
    def default_frequency():
        return 'yearly'

    @staticmethod
    def default_term_date_choice():
        return 'subscription'

    @staticmethod
    def default_date_for_sync():
        return utils.today()

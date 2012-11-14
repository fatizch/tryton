#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.modules.coop_utils import model, business
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot
from trytond.modules.insurance_product.product import CONFIG_KIND
from trytond.modules.insurance_product import EligibilityResultLine

__all__ = [
    'EligibilityRule',
    'EligibilityRelationKind'
    ]

SUBSCRIBER_CLASSES = [
    ('party.person', 'Person'),
    ('party.company', 'Company'),
    ('party.party', 'All'),
    ]


class EligibilityRule(model.CoopSQL, BusinessRuleRoot):
    'Eligibility Rule'

    __name__ = 'ins_product.eligibility_rule'
    sub_elem_config_kind = fields.Selection(CONFIG_KIND,
        'Sub Elem Conf. kind', required=True)
    sub_elem_rule = fields.Many2One('rule_engine', 'Sub Elem Rule Engine',
        depends=['config_kind'])
    subscriber_classes = fields.Selection(
        SUBSCRIBER_CLASSES,
        'Can be subscribed',
        required=True)
    relation_kinds = fields.Many2Many('ins_product.eligibility_relation_kind',
        'eligibility_rule', 'relation_kind', 'Relations Authorized')

    def give_me_eligibility(self, args):
        # First of all, we look for a subscriber data in the args and update
        # the args dictionnary for sub values.
        try:
            business.update_args_with_subscriber(args)
        except business.ArgsDoNotMatchException:
            # If no Subscriber is found, automatic refusal
            return (EligibilityResultLine(
                False, ['Subscriber not defined in args']), [])

        # We define a match_table which will tell what data to look for
        # depending on the subscriber_eligibility attribute value.
        match_table = {
            'party.party': 'subscriber',
            'party.person': 'subscriber_person',
            'party.company': 'subscriber_company'}

        # if it does not match, refusal
        if not match_table[self.subscriber_classes] in args:
            return (EligibilityResultLine(
                False,
                ['Subscriber must be a %s'
                    % dict(SUBSCRIBER_CLASSES)[self.subscriber_classes]]),
                [])

        # Now we can call the rule if it exists :
        if hasattr(self, 'rule') and self.rule:
            res, mess, errs = self.rule.compute(args)
            return (EligibilityResultLine(eligible=res, details=mess), errs)

        # Default eligibility is "True" :
        return (
            EligibilityResultLine(eligible=True),
            [])

    def give_me_sub_elem_eligibility(self, args):
        if hasattr(self, 'sub_elem_rule') and self.sub_elem_rule:
            res, mess, errs = self.sub_elem_rule.compute(args)
            return (EligibilityResultLine(eligible=res, details=mess), errs)
        return (EligibilityResultLine(True), [])

    @staticmethod
    def default_is_eligible():
        return True

    @staticmethod
    def default_is_sub_elem_eligible():
        return True

    @staticmethod
    def default_sub_elem_config_kind():
        return 'simple'

    @staticmethod
    def default_subscriber_classes():
        return 'party.person'


class EligibilityRelationKind(model.CoopSQL):
    'Define relation between eligibility rule and relation kind authorized'

    __name__ = 'ins_product.eligibility_relation_kind'

    eligibility_rule = fields.Many2One('ins_product.eligibility_rule',
        'Eligibility Rule', ondelete='CASCADE')
    relation_kind = fields.Many2One('party.party_relation_kind',
        'Relation Kind', ondelete='CASCADE')

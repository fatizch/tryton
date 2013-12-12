#-*- coding:utf-8 -*-
from trytond.pyson import Eval, Or
from trytond.modules.coop_utils import model, fields, utils
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot
from trytond.modules.offered.offered import CONFIG_KIND
from trytond.modules.offered import EligibilityResultLine

__all__ = [
    'EligibilityRule',
    'EligibilityRelationKind'
]

SUBSCRIBER_CLASSES = [
    ('person', 'Person'),
    ('company', 'Society'),
    ('all', 'All'),
]


class EligibilityRule(BusinessRuleRoot, model.CoopSQL):
    'Eligibility Rule'

    __name__ = 'offered.eligibility.rule'

    sub_elem_config_kind = fields.Selection(
        CONFIG_KIND, 'Sub Elem Conf. kind', states={
            'invisible': Eval('offered_kind') != 'offered.coverage',
            'required': Eval('offered_kind') == 'offered.coverage',
        })
    sub_elem_rule = fields.Many2One(
        'rule_engine', 'Sub Elem Rule Engine', depends=['config_kind'],
        states={
            'invisible': Eval('offered_kind') != 'offered.coverage',
        })
    sub_elem_rule_complementary_data = fields.Dict(
        'offered.complementary_data_def', 'Rule Complementary Data',
        on_change_with=['sub_elem_rule', 'sub_elem_rule_complementary_data'],
        states={
            'invisible': Eval('offered_kind') != 'offered.coverage',
        })
    subscriber_classes = fields.Selection(SUBSCRIBER_CLASSES,
        'Can be subscribed', states={
            'invisible': Eval('offered_kind') == 'benefit',
            'required': Eval('offered_kind') != 'benefit',
        })
    relation_kinds = fields.Many2Many(
        'offered.eligibility.rule-relation.kind',
        'eligibility_rule', 'relation_kind', 'Relations Authorized',
        states={
            'invisible': Or(
                Eval('sub_elem_config_kind') != 'simple',
                Eval('offered_kind') != 'offered.coverage',
            )
        }, depends=['sub_elem_config_kind'])
    offered_kind = fields.Function(
        fields.Char('Offered Kind', states={'invisible': True},
            on_change_with=['offered']),
        'on_change_with_offered_kind')

    def give_me_eligibility(self, args):
        # Now we can call the rule if it exists :
        if hasattr(self, 'rule') and self.rule:
            rule_result = self.get_rule_result(args)
            return (
                EligibilityResultLine(
                    eligible=rule_result.result,
                    details=rule_result.print_warnings()),
                rule_result.print_errors())

        # Default eligibility is "True" :
        return EligibilityResultLine(eligible=True), []

    def give_me_sub_elem_eligibility(self, args):
        if hasattr(self, 'sub_elem_rule') and self.sub_elem_rule:
            result = self.sub_elem_rule.execute(args)
            return (EligibilityResultLine(eligible=result.result,
                    details=result.warnings), result.errors)
        return (EligibilityResultLine(True), [])

    def on_change_with_sub_elem_rule_complementary_data(self):
        if not (hasattr(self, 'sub_elem_rule') and self.sub_elem_rule):
            return {}
        return self.sub_elem_rule.get_complementary_data_for_on_change(
            self.sub_elem_rule_complementary_data)

    def get_rule_complementary_data(self, schema_name):
        if not (hasattr(self, 'sub_elem_rule_complementary_data') and
                self.sub_elem_rule_complementary_data):
            result = None
        else:
            result = self.sub_elem_rule_complementary_data.get(
                schema_name, None)
        if not result:
            return super(EligibilityRule, self).get_rule_complementary_data(
                schema_name)
        return result

    @staticmethod
    def default_is_sub_elem_eligible():
        return True

    @staticmethod
    def default_sub_elem_config_kind():
        return 'simple'

    @staticmethod
    def default_subscriber_classes():
        return 'person'

    def on_change_with_offered_kind(self, name):
        res = ''
        if self.offered:
            res = self.offered.__name__
        return res


class EligibilityRelationKind(model.CoopSQL):
    'Define relation between eligibility rule and relation kind authorized'

    __name__ = 'offered.eligibility.rule-relation.kind'

    eligibility_rule = fields.Many2One(
        'offered.eligibility.rule', 'Eligibility Rule', ondelete='CASCADE')
    relation_kind = fields.Many2One(
        'party.relation.kind', 'Relation Kind', ondelete='CASCADE')

#-*- coding:utf-8 -*-
from trytond.pyson import Eval, Or
from trytond.modules.coop_utils import model, business, fields, utils
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot
from trytond.modules.offered.offered import CONFIG_KIND
from trytond.modules.insurance_product import EligibilityResultLine

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

    __name__ = 'ins_product.eligibility_rule'

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
            'invisible': Eval('offered_kind') == 'ins_product.benefit',
            'required': Eval('offered_kind') != 'ins_product.benefit',
        })
    relation_kinds = fields.Many2Many(
        'ins_product.eligibility_relation_kind',
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

    def check_subscriber_classes(self, args):
        if self.offered_kind != 'ins_product.benefit':
            # We define a match_table which will tell what data to look for
            # depending on the subscriber_eligibility attribute value.
            match_table = {
                'all': 'subscriber',
                'person': 'subscriber_person',
                'company': 'subscriber_company'}

            # if it does not match, refusal
            if not match_table[self.subscriber_classes] in args:
                return (False, ['Subscriber must be a %s'
                        % dict(SUBSCRIBER_CLASSES)[self.subscriber_classes]])
        return True, []

    def give_me_eligibility(self, args):
        # First of all, we look for a subscriber data in the args and update
        # the args dictionnary for sub values.
        try:
            business.update_args_with_subscriber(args)
        except business.ArgsDoNotMatchException:
            # If no Subscriber is found, automatic refusal
            return (EligibilityResultLine(
                False, ['Subscriber not defined in args']), [])

        res, errs = self.check_subscriber_classes(args)
        if not res:
            return EligibilityResultLine(False, [], errs)

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
            res, mess, errs = utils.execute(self, self.sub_elem_rule, args)
            return (EligibilityResultLine(eligible=res, details=mess), errs)
        return (EligibilityResultLine(True), [])

    def on_change_with_sub_elem_rule_complementary_data(self):
        if not (hasattr(self, 'sub_elem_rule') and self.sub_elem_rule):
            return {}
        if not (hasattr(self.sub_elem_rule, 'complementary_parameters') and
                self.sub_elem_rule.complementary_parameters):
            return {}
        return dict([
            (elem.name, self.sub_elem_rule_complementary_data.get(
                elem.name, elem.get_default_value(None)))
            for elem in self.sub_elem_rule.complementary_parameters])

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

    __name__ = 'ins_product.eligibility_relation_kind'

    eligibility_rule = fields.Many2One(
        'ins_product.eligibility_rule', 'Eligibility Rule', ondelete='CASCADE')
    relation_kind = fields.Many2One(
        'party.party_relation_kind', 'Relation Kind', ondelete='CASCADE')

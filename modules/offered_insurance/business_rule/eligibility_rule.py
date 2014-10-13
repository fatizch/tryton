# -*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.modules.cog_utils import model, fields, utils
from trytond.modules.offered_insurance.business_rule.business_rule import \
    BusinessRuleRoot
from trytond.modules.offered.offered import CONFIG_KIND
from trytond.modules.offered import EligibilityResultLine

__all__ = [
    'EligibilityRule',
    ]


class EligibilityRule(BusinessRuleRoot, model.CoopSQL):
    'Eligibility Rule'

    __name__ = 'offered.eligibility.rule'

    sub_elem_config_kind = fields.Selection(CONFIG_KIND, 'Sub Elem Conf. kind',
        states={
            'invisible': Eval('offered_kind') != 'offered.option.description',
            'required': Eval('offered_kind') == 'offered.option.description',
            })
    sub_elem_rule = fields.Many2One('rule_engine', 'Sub Elem Rule Engine',
        depends=['config_kind'], ondelete='RESTRICT', states={
            'invisible': Eval('offered_kind') != 'offered.option.description',
            })
    sub_elem_rule_extra_data = fields.Dict('rule_engine.rule_parameter',
        'Rule Parameters', states={
            'invisible': Eval('offered_kind') != 'offered.option.description',
            })
    subscriber_classes = fields.Selection([
            ('person', 'Person'),
            ('company', 'Society'),
            ('all', 'All'),
            ], 'Can be subscribed', states={
            'invisible': Eval('offered_kind') == 'benefit',
            'required': Eval('offered_kind') != 'benefit',
            })
    offered_kind = fields.Function(
        fields.Char('Offered Kind', states={'invisible': True}),
        'on_change_with_offered_kind')

    @classmethod
    def __setup__(cls):
        super(EligibilityRule, cls).__setup__()
        # TODO : Remove this once we use M2O rather than a Reference field
        utils.update_selection(cls, 'offered', (('benefit', 'Benefit'),))

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
            result = self.sub_elem_rule.execute(args,
                self.sub_elem_rule_extra_data)
            return (EligibilityResultLine(eligible=result.result,
                    details=result.warnings), result.errors)
        return (EligibilityResultLine(True), [])

    @fields.depends('sub_elem_rule', 'sub_elem_rule_extra_data')
    def on_change_with_sub_elem_rule_extra_data(self):
        if not (hasattr(self, 'sub_elem_rule') and self.sub_elem_rule):
            return {}
        return self.sub_elem_rule.get_extra_data_for_on_change(
            self.sub_elem_rule_extra_data)

    def get_rule_extra_data(self, schema_name):
        if not (hasattr(self, 'sub_elem_rule_extra_data') and
                self.sub_elem_rule_extra_data):
            result = None
        else:
            result = self.sub_elem_rule_extra_data.get(
                schema_name, None)
        if not result:
            return super(EligibilityRule, self).get_rule_extra_data(
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

    @fields.depends('offered')
    def on_change_with_offered_kind(self, name):
        res = ''
        if self.offered:
            res = self.offered.__name__
        return res

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import And, Eval, Or, Bool
from trytond.server_context import ServerContext
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, model, utils, coog_string
from trytond.modules.rule_engine.rule_engine import RuleEngineResult
from trytond.modules.claim_indemnification \
    import BenefitRule as OriginalBenefitRule


__all__ = [
    'Benefit',
    'BenefitCompanyProduct',
    'BenefitRule',
    'BenefitRuleIndemnification',
    'BenefitRuleDeductible',
    'BenefitRuleRevaluation',
    ]


class Benefit(metaclass=PoolMeta):
    __name__ = 'benefit'

    company_products = fields.Many2Many('benefit-company_product', 'benefit',
        'product', 'Company Products',
        domain=[('template.taxes_included', '!=', True)],
        help='Products available when paying a company')

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls._error_messages.update({
                'subsidiaries_then_covered_enum': 'Subsidiaries then Covered',
                'subsidiaries_covered_subscriber_enum': 'Subsidiaries, Covered'
                ' and Subscriber',
                })

    @classmethod
    def get_beneficiary_kind(cls):
        return super(Benefit, cls).get_beneficiary_kind() + [
            ('subsidiaries_then_covered', cls.raise_user_error(
                    'subsidiaries_then_covered_enum', raise_exception=False)),
            ('subsidiaries_covered_subscriber', cls.raise_user_error(
                    'subsidiaries_covered_subscriber_enum',
                    raise_exception=False)),
            ]

    def _extra_data_structure(self):
        base = super(Benefit, self)._extra_data_structure()
        service = ServerContext().get('service', None)
        if not service or not service.benefit.is_group:
            return base
        version = service.option.get_version_at_date(service.loss.get_date())
        option_benefit = version.get_benefit(service.benefit)
        base.update(option_benefit._extra_data_structure())
        return base

    def get_benefit_accounts(self):
        accounts = super(Benefit, self).get_benefit_accounts()
        if not self.is_group:
            return accounts
        return accounts + [
            x.account_expense_used for x in self.company_products
            if x.account_expense_used]

    def get_documentation_structure(self):
        doc = super(Benefit, self).get_documentation_structure()
        if self.is_group:
            doc['parameters'].append(
                coog_string.doc_for_field(self, 'company_products'))
        return doc


class BenefitCompanyProduct(model.CoogSQL):
    'Benefit Company Product relation'

    __name__ = 'benefit-company_product'

    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        ondelete='RESTRICT')


class BenefitRule(metaclass=PoolMeta):
    __name__ = 'benefit.rule'

    indemnification_rules = fields.Many2Many(
        'benefit_rule-indemnification_rule', 'benefit', 'rule',
        'Indemnification Rules', states={
            'invisible': Eval('force_indemnification_rule', False)},
        depends=['force_indemnification_rule'])
    deductible_rules = fields.Many2Many('benefit_rule-deductible_rule',
        'benefit', 'rule', 'Deductible Rules', states={
            'invisible': Eval('force_deductible_rule', False)},
        depends=['force_deductible_rule'])
    revaluation_rules = fields.Many2Many('benefit_rule-revaluation_rule',
        'benefit', 'rule', 'Revaluation Rules', states={
            'invisible': Eval('force_revaluation_rule', False)},
        depends=['force_revaluation_rule'])
    force_indemnification_rule = fields.Function(
        fields.Boolean('Force Indemnification Rule',
            states={'invisible': ~Eval('is_group')},
            depends=['is_group']),
        'get_force_rule', setter='setter_void')
    force_deductible_rule = fields.Function(
        fields.Boolean('Force Deductible Rule',
            states={'invisible': ~Eval('is_group')},
            depends=['is_group']),
        'get_force_rule', setter='setter_void')
    force_annuity_frequency = fields.Boolean(
        'Force Annuity Frenquency',
        help='Get annuity frequency from product if True',
        states={'invisible': ~Eval('is_group') | ~Eval('requires_frequency')},
        depends=['is_group', 'requires_frequency'])
    force_revaluation_rule = fields.Function(
        fields.Boolean('Force Revaluation Rule',
            states={'invisible': ~Eval('is_group')},
            depends=['is_group']),
        'get_force_rule', setter='setter_void')
    is_group = fields.Function(
        fields.Boolean('Is Group'),
        'get_is_group')

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        cls._error_messages.update({
                'multiple_indemnification_rules': 'Multiple indemnification '
                'rules allowed',
                'amount_revaluation': 'Amount is replaced by revaluation '
                'amount.',
                'previous_insurer_desc': 'Computed amount transfered by the '
                'previous insurer: %(computation)s',
                })
        cls.indemnification_rule.states['invisible'] = And(
            cls.indemnification_rule.states.get('invisible', True),
            ~Eval('force_indemnification_rule'))
        cls.indemnification_rule.depends.append('force_indemnification_rule')
        cls.indemnification_rule_extra_data.states['invisible'] = Or(
            cls.indemnification_rule_extra_data.states.get('invisible', True),
            ~Eval('force_indemnification_rule'))
        cls.indemnification_rule_extra_data.depends.append(
            'force_indemnification_rule')
        cls.deductible_rule.states['invisible'] = And(
            cls.deductible_rule.states.get('invisible',
                True), ~Eval('force_deductible_rule'))
        cls.deductible_rule.depends.append('force_deductible_rule')
        cls.deductible_rule_extra_data.states['invisible'] = Or(
            cls.deductible_rule_extra_data.states.get('invisible',
                True), ~Eval('force_deductible_rule'))
        cls.deductible_rule_extra_data.depends.append('force_deductible_rule')
        cls.revaluation_rule.states['invisible'] = And(
            cls.revaluation_rule.states.get('invisible',
                True), ~Eval('force_revaluation_rule'))
        cls.revaluation_rule.depends.append('force_revaluation_rule')
        cls.revaluation_rule_extra_data.states['invisible'] = Or(
            cls.revaluation_rule_extra_data.states.get('invisible',
                True), ~Eval('force_revaluation_rule'))
        cls.revaluation_rule_extra_data.depends.append(
            'force_revaluation_rule')
        cls.annuity_frequency.states['invisible'] = Or(
                cls.annuity_frequency.states.get('invisible'),
                And(Bool(Eval('is_group')), ~Eval('force_annuity_frequency')))
        cls.annuity_frequency.states['required'] = And(
                cls.annuity_frequency.states.get('required', False),
                Bool(Eval('force_annuity_frequency')))
        cls.annuity_frequency.depends.extend(['force_annuity_frequency',
            'is_group'])

    def get_rec_name(self, name):
        if not self.indemnification_rule and self.indemnification_rules:
            return self.raise_user_error('multiple_indemnification_rules',
                raise_exception=False)
        return super(BenefitRule, self).get_rec_name(name)

    @classmethod
    def default_force_annuity_frequency(cls):
        return True

    @classmethod
    def default_force_deductible_rule(cls):
        return True

    @classmethod
    def default_force_indemnification_rule(cls):
        return True

    @classmethod
    def default_force_revaluation_rule(cls):
        return True

    @fields.depends('benefit', 'is_group')
    def on_change_benefit(self):
        super(BenefitRule, self).on_change_benefit()
        self.is_group = self.benefit.is_group if self.benefit else False

    def _on_change_rule(self, rule_name):
        if getattr(self, 'force_' + rule_name, None):
            setattr(self, rule_name, None)
            setattr(self, rule_name + '_extra_data', {})
            setattr(self, rule_name + 's', [])
        else:
            setattr(self, rule_name + 's', [getattr(self, rule_name)]
                if getattr(self, rule_name) else [])
            setattr(self, rule_name, None)
            setattr(self, rule_name + '_extra_data', {})

    @fields.depends('deductible_rule', 'deductible_rule_extra_data',
        'deductible_rules', 'force_deductible_rule')
    def on_change_force_deductible_rule(self):
        self._on_change_rule('deductible_rule')

    @fields.depends('force_indemnification_rule', 'indemnification_rules',
        'indemnification_rule', 'indemnification_rule_extra_data')
    def on_change_force_indemnification_rule(self):
        self._on_change_rule('indemnification_rule')

    @fields.depends('revaluation_rule', 'revaluation_rule_extra_data',
        'revaluation_rules', 'force_revaluation_rule')
    def on_change_force_revaluation_rule(self):
        self._on_change_rule('revaluation_rule')

    def get_force_rule(self, name):
        return bool(getattr(self, name[6:]))

    def get_is_group(self, name):
        return self.benefit.is_group

    def _calculate_rule(self, rule_name, args, default_value, **kwargs):
        option = args.get('option', None)
        if not option or getattr(self, 'force_' + rule_name):
            return getattr(OriginalBenefitRule, 'calculate_' + rule_name)(
                self, args, **kwargs)
        # Use option defined rule
        version = option.get_version_at_date(args['date'])
        option_benefit = version.get_benefit(self.benefit)
        if not option_benefit or not getattr(option_benefit, rule_name):
            return default_value
        return getattr(option_benefit, 'calculate_' + rule_name)(args,
            **kwargs)

    def calculate_deductible_rule(self, args, **kwargs):
        return self._calculate_rule('deductible_rule', args,
            RuleEngineResult(datetime.date.min), **kwargs)

    def calculate_indemnification_rule(self, args, **kwargs):
        return self._calculate_rule('indemnification_rule', args, [], **kwargs)

    def calculate_revaluation_rule(self, args, **kwargs):
        return self._calculate_rule('revaluation_rule', args, [], **kwargs)

    def must_revaluate(self):
        if Transaction().context.get('force_no_revaluation', False):
            return False
        if self.force_indemnification_rule:
            return super(BenefitRule, self).must_revaluate()
        return bool(self.revaluation_rules)

    def _get_previous_insurer_amount_benefits(self, service, start_date,
            end_date, previous_insurer_amount, indemnification):
        description = ''

        if self.benefit.indemnification_kind == 'period':
            nb_of_unit = (end_date - start_date).days + 1
            str_nb_of_unit = coog_string.format_number('%.2f', nb_of_unit)
            amount = previous_insurer_amount * nb_of_unit
            str_amount = coog_string.format_number('%.2f', amount)
            previous_insurer_desc = '%s = %s * %s\n' % (str_amount,
                previous_insurer_amount, str_nb_of_unit)
            description += self.raise_user_error('previous_insurer_desc', {
                    'computation': previous_insurer_desc,
                    }, raise_exception=False)
            return [{
                    'start_date': start_date,
                    'end_date': end_date,
                    'nb_of_unit': nb_of_unit,
                    'unit': 'day',
                    'amount': amount,
                    'base_amount': previous_insurer_amount,
                    'amount_per_unit': previous_insurer_amount,
                    'description': description,
                    'limit_date': None,
                    'extra_details': {},
                    }]
        elif self.benefit.indemnification_kind == 'annuity':
            frequency = indemnification.service.annuity_frequency
            annual_previous_insurer_amount = previous_insurer_amount
            periods = indemnification.service.calculate_annuity_periods(
                start_date, end_date)
            rounding_factor = (
                Decimal(1) / 10 ** indemnification.currency_digits)
            return self.get_ltd_periods(periods,
                annual_previous_insurer_amount, frequency, description,
                rounding_factor, None)
        return []

    def do_calculate_indemnification_rule(self, args):
        delivered = args['service']
        start_date = args['indemnification_detail_start_date']
        end_date = args['indemnification_detail_end_date']
        version = utils.get_value_at_date(delivered.extra_datas, start_date)
        if not version.previous_insurer_base_amount:
            return super(BenefitRule, self).do_calculate_indemnification_rule(
                args)
        return self._get_previous_insurer_amount_benefits(delivered,
            start_date, end_date, version.previous_insurer_base_amount,
            args['indemnification'])

    def do_calculate_revaluation_rule(self, args):
        delivered = args['service']

        if (delivered.is_a_complement and
                delivered.option.previous_claims_management_rule ==
                'in_complement_previous_rule'):
            # The rule that should be used to compute the revaluation must be
            # that of the previous service
            assert delivered.origin_service
            origin = delivered.origin_service

            rule = origin.benefit.benefit_rules
            if not rule:
                return

            args = args.copy()
            origin.init_dict_for_rule_engine(args)
            return rule[0].do_calculate_revaluation_rule(args)

        start_date = args['indemnification_detail_start_date']
        extra_data = utils.get_value_at_date(delivered.extra_datas, start_date)
        res = super(BenefitRule, self).do_calculate_revaluation_rule(args)
        if not extra_data.previous_insurer_base_amount:
            return res

        for benefit in res:
            benefit['amount_per_unit'] -= (
                extra_data.previous_insurer_base_amount +
                extra_data.previous_insurer_revaluation)
            benefit['base_amount'] = Decimal('0')
            benefit['amount'] = benefit['amount_per_unit'] * \
                benefit['nb_of_unit']
            benefit['extra_details']['montant_revalorisation'] = \
                benefit['amount_per_unit']
        return res


class BenefitRuleIndemnification(model.CoogSQL):
    'Benefit Rule - Indemnification'

    __name__ = 'benefit_rule-indemnification_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')


class BenefitRuleDeductible(model.CoogSQL):
    'Benefit Rule - Deductible'

    __name__ = 'benefit_rule-deductible_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')


class BenefitRuleRevaluation(model.CoogSQL):
    'Benefit Rule - Revaluation'

    __name__ = 'benefit_rule-revaluation_rule'

    benefit = fields.Many2One('benefit.rule', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='RESTRICT')

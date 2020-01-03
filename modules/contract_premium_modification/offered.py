# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql import Table, Literal
from decimal import Decimal

from trytond import backend
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
from trytond.cache import Cache

from trytond.modules.coog_core import fields, model, utils, coog_string
from trytond.modules.rule_engine import get_rule_mixin

from .exceptions import WaiverDiscountValidationError

__all__ = [
    'Product',
    'OptionDescription',
    'WaiverPremiumRule',
    'WaiverPremiumRuleTaxRelation',
    ]


class PremiumModificationRuleMixin(
        get_rule_mixin('duration_rule', 'Duration Rule',
            extra_string='Duration Rule Extra Data'),
        get_rule_mixin('eligibility_rule', 'Eligibility Rule'),
        model.ConfigurationMixin):

    automatic = fields.Boolean("Automatic")
    rate = fields.Numeric("Rate", digits=(16, 4),
        domain=[('rate', '>', 0), ('rate', '<=', 1)])
    account_for_modification = fields.Many2One('account.account',
        "Account to compensate the Modification", ondelete='RESTRICT',
        domain=[
            ('type.receivable', '=', False),
            ('type.payable', '=', False)
            ])
    invoice_line_period_behaviour = fields.Selection([
            ('one_day_overlap', 'One Day Overlap'),
            ('total_overlap', 'Total Overlap'),
            ('proportion', 'Proportion'),
            ], 'Invoice Line Period Behaviour', help='Defines the behaviour '
            'between the invoice line period vs the waiver of premium period '
            'One Day Overlap allows a full waiver of premium if there is at '
            'least one day overlap, Total Overlap allows a waiver of premium '
            'only if the whole invoice line period is within the waiver period,'
            ' Proportion allows a waiver of premium proportional to the ratio '
            'between the waiver period and the invoice line period'
            )

    @classmethod
    def default_rate(cls):
        return Decimal(1)

    @classmethod
    def default_invoice_line_period_behaviour(cls):
        return 'total_overlap'

    # As taxes have to use their own M2M relation table defining a taxes field
    # is not suitable for the Mixin
    @property
    def modification_taxes(self):
        raise NotImplementedError

    @classmethod
    def get_modification_line_fields(cls):
        raise NotImplementedError

    @classmethod
    def get_modification_line_detail_fields(cls):
        raise NotImplementedError

    def get_account_for_modification_line(self, line):
        raise NotImplementedError

    def get_rule_documentation_structure(self):
        doc = [
            coog_string.doc_for_field(self, 'rate'),
            coog_string.doc_for_field(self, 'automatic'),
            coog_string.doc_for_field(self, 'invoice_line_period_behaviour'),
            # classes implementing PremiumModificationRuleMixin must have a
            # taxes field but as it is a M2M it can not be defined here
            coog_string.doc_for_field(self, 'taxes'),
            coog_string.doc_for_field(self, 'account_for_modification'),
            ]
        if self.duration_rule:
            doc.append(
                self.get_duration_rule_rule_engine_documentation_structure())
        return doc

    def init_modification_line(self, line, modification_ctx):
        line.taxes = [x.id for x in self.modification_taxes]
        line.account = self.get_account_for_modification_line(line)
        modification_start = (modification_ctx.get('start_date')
            or datetime.date.min)
        modification_end = modification_ctx.get('end_date') or datetime.date.max
        fully_exonerated = (modification_start <= line.coverage_start
            and modification_end >= line.coverage_end)
        premium = getattr(line.details[0], 'premium', None)
        if not premium:
            return line
        currency = premium.main_contract.company.currency
        if (self.invoice_line_period_behaviour == 'proportion'
                and not fully_exonerated):
            line.coverage_start = max(line.coverage_start, modification_start)
            line.coverage_end = min(line.coverage_end, modification_end)
            line.unit_price = -1 * utils.get_prorated_amount_on_period(
                line.coverage_start, line.coverage_end,
                frequency=premium.frequency, value=premium.amount,
                sync_date=premium.main_contract.start_date,
                interval_start=premium.start,
                proportion=True, recursion=True
                ) * self.rate
        else:
            line.unit_price *= -1 * self.rate
        line.unit_price = currency.round(line.unit_price)
        if modification_ctx.get('is_waiver'):
            line.description += ' - ' + gettext(
                'contract_premium_modification.msg_waiver_line')
        else:
            line.description += modification_ctx.get('discount_description')
        return line

    def eligible(self, option, modifications):
        raise NotImplementedError


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    _must_invoice_after_contract_end_cache = Cache(
        '_must_invoice_after_contract')

    @property
    def _must_invoice_after_contract(self):
        '''
            The goal of this method is to detect a specific configuration case,
            in order to behave properly when the associated contracts are
            terminated.

            The case is as follow:
                - The global configuration for prorating premiums is
                  deactivated
                - There are waivers configured on the coverages that must be
                  prorated

            The edge case we want to fix is:
                - A 300 $ invoice paid quarterly is due from the 01-01 to the
                  03-31
                - There is a prorated waiver on this invoice from the 02-01 to
                  the 03-31
            The expected amount is 300 * (1 - 2/3) == 100 $, which is indeed
            the case.

            The problem occurs if the contract is terminated for instance the
            01-15. The invoice is then calculated from the 01-01 to the 01-15,
            and is worth 300 $ since the premium is not prorated. However,
            because the invoice ends on the 01-15, the waiver is not used, so
            the user have to actually pay 300 $ for a 15 days invoice.

            The proposed solution is, in this specific case, to ignore the
            contract end date when calculating the last invoice period, and use
            the full calculated period. So in the previous example, the invoice
            period would actually be 01-01 to 03-31, even though the contract
            terminates on the 01-15. Doing so will make it be calculated as
            expected.
        '''
        value = self.__class__._must_invoice_after_contract_end_cache.get(
            self.id, -1)
        if value != -1:
            return value
        if Pool().get('offered.configuration').get_cached_prorate_premiums():
            self.__class__._must_invoice_after_contract_end_cache.set(
                self.id, False)
            return False
        for coverage in self.coverages:
            if not coverage.with_waiver_of_premium:
                continue
            if (coverage.waiver_premium_rule[0].invoice_line_period_behaviour ==
                    'proportion'):
                self.__class__._must_invoice_after_contract_end_cache.set(
                    self.id, True)
                return True
        self.__class__._must_invoice_after_contract_end_cache.set(
            self.id, False)
        return False


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    with_waiver_of_premium = fields.Function(
        fields.Boolean('With Waiver Of Premium'),
        'get_with_waiver_of_premium')
    with_discount_of_premium = fields.Function(
        fields.Boolean('With Discount of Premium'),
        'get_with_discount_of_premium')
    with_modifications_of_premium = fields.Function(
        fields.Boolean('With Premium Modifications'),
        'get_with_modifications_of_premium')
    waiver_premium_rule = fields.One2Many(
        'waiver_premium.rule', 'coverage',
        'Waiver Of Premium Rule', help='Define how waiver of premium can be '
        'processed on this option',
        delete_missing=True, size=1)
    discount_rules = fields.Many2Many(
        'commercial_discount.rule-option.description',
        'coverage', 'rule', "Discount Rules",
        readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._function_auto_cache_fields.append('with_waiver_of_premium')
        cls._function_auto_cache_fields.append('with_discount_of_premium')
        cls._function_auto_cache_fields.append('with_modifications_of_premium')

    @classmethod
    def validate(cls, coverages):
        super().validate(coverages)
        cls.check_waiver_discounts()

    @classmethod
    def check_waiver_discounts(cls):
        pool = Pool()
        WaiverRule = pool.get('waiver_premium.rule')
        DiscountRuleCoverage = pool.get(
            'commercial_discount.rule-option.description')

        waiver_rule = WaiverRule.__table__()
        discount_rule = DiscountRuleCoverage.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*discount_rule.join(waiver_rule,
                condition=waiver_rule.coverage == discount_rule.coverage
                ).select(discount_rule.coverage))
        if cursor.fetchone():
            raise WaiverDiscountValidationError(gettext(
                    'contract_premium_modification'
                    '.msg_waiver_discount_coverage'))

    def get_with_waiver_of_premium(self, name):
        return bool(self.waiver_premium_rule)

    def get_with_discount_of_premium(self, name):
        return bool(self.discount_rules)

    def get_with_modifications_of_premium(self, name):
        return bool(self.premium_modification_rules)

    @property
    def premium_modification_rules(self):
        return self.discount_rules + self.waiver_premium_rule

    def get_documentation_structure(self):
        structure = super(OptionDescription, self).get_documentation_structure()
        structure['rules'].append(
            coog_string.doc_for_rules(self, 'waiver_premium_rule'))
        return structure

    def is_discount_allowed(self, discount):
        return discount in {rule.commercial_discount
            for rule in self.discount_rules}


class WaiverPremiumRule(
        PremiumModificationRuleMixin, model.CoogSQL, model.CoogView):
    'Waiver of Premium Rule'

    _func_key = 'func_key'
    __name__ = 'waiver_premium.rule'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    taxes = fields.Many2Many('waiver_premium.rule-account.tax',
        'waiver_rule', 'tax', 'Taxes')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE', select=True)

    @classmethod
    def __register__(cls, module):
        super(WaiverPremiumRule, cls).__register__(module)
        # Migration from 1.12 Move Waiver Premium configuration to extra table
        TableHandler = backend.get('TableHandler')
        Coverage = Pool().get('offered.option.description')
        coverage_h = TableHandler(Coverage, module)
        if not coverage_h.column_exist('with_waiver_of_premium'):
            return

        waiver = cls.__table__()
        coverage = Coverage.__table__()
        cursor = Transaction().connection.cursor()
        query = waiver.insert(columns=[waiver.coverage, waiver.rate,
                waiver.invoice_line_period_behaviour],
            values=coverage.select(coverage.id, Literal(1),
                    Literal('one_day_overlap'),
                    where=(coverage.with_waiver_of_premium ==
                        'with_waiver_of_premium')))
        cursor.execute(*query)

        coverage_h.drop_column('with_waiver_of_premium')

        # Migration from 2.4 Add Discounts on Premium
        query = waiver.update(
            [waiver.account_for_modification], [waiver.account_for_waiver])
        cursor.execute(*query)

    @classmethod
    def __setup__(cls):
        super(WaiverPremiumRule, cls).__setup__()
        cls.duration_rule.domain = [('type_', '=', 'waiver_duration')]
        cls.duration_rule.help = \
            'Returns a list containing the start and the end date'
        cls.duration_rule.states['required'] = Bool(Eval('automatic'))
        cls.duration_rule.depends += ['automatic']

    @classmethod
    def validate(cls, waivers):
        pool = Pool()
        Coverage = pool.get('offered.option.description')

        super().validate(waivers)
        Coverage.check_waiver_discounts()

    @classmethod
    def _export_light(cls):
        return super(WaiverPremiumRule, cls)._export_light() | {
            'duration_rule'}

    def get_func_key(self, name):
        return self.coverage.code + '|' + self.duration_rule.short_name

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                coverage_code, short_name = clause[2].split('|')
                return [('coverage.code', clause[1], coverage_code),
                    ('duration_rule.short_name', clause[1], short_name)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('coverage.code',) + tuple(clause[1:])],
                [('duration_rule.short_name',) + tuple(clause[1:])],
                ]

    @property
    def modification_taxes(self):
        return self.taxes

    @property
    def modification(self):
        return self

    @classmethod
    def get_modification_line_fields(cls):
        return {
            'type', 'description', 'origin', 'quantity', 'unit', 'unit_price',
            'invoice_type', 'coverage_start', 'coverage_end', 'coverage',
            }

    @classmethod
    def get_modification_line_detail_fields(cls):
        return {
            'rated_entity', 'frequency', 'rate', 'premium', 'loan', 'coverage',
            }

    def get_account_for_modification_line(self, line):
        if self.account_for_modification:
            return self.account_for_modification
        else:
            return self.coverage.get_account_for_billing(line)

    def eligible(self, option, modifications):
        return True


class WaiverPremiumRuleTaxRelation(model.ConfigurationMixin):
    'Option Description Tax Relation For Waiver'

    __name__ = 'waiver_premium.rule-account.tax'

    waiver_rule = fields.Many2One('waiver_premium.rule', 'Waiver Premium Rule',
        ondelete='CASCADE', required=True, select=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
        required=True)

    @classmethod
    def __register__(cls, module):
        # Migration from 1.12 Move Waiver Premium configuration to extra table
        TableHandler = backend.get('TableHandler')
        super(WaiverPremiumRuleTaxRelation, cls).__register__(module)
        if not TableHandler.table_exist('coverage-account_tax-for_waiver'):
            return

        relation = cls.__table__()
        waiver = Pool().get('waiver_premium.rule').__table__()
        old_relation = Table('coverage-account_tax-for_waiver')

        cursor = Transaction().connection.cursor()
        cursor.execute(*relation.insert(
                columns=[relation.waiver_rule, relation.tax],
                values=waiver.join(old_relation,
                    condition=(old_relation.coverage == waiver.coverage),
                    ).select(waiver.id, old_relation.tax)))
        TableHandler.drop_table('coverage-account_tax-for_waiver',
            'coverage-account_tax-for_waiver')


class CommercialDiscount(model.CodedMixin, model.CoogView, model.CoogSQL):
    "Commercial Discount"
    __name__ = 'commercial_discount'

    rules = fields.One2Many(
        'commercial_discount.rule', 'commercial_discount',
        "Rules", delete_missing=True)

    @classmethod
    def validate(cls, discounts):
        super().validate(discounts)
        for discount in discounts:
            if len({bool(rule.automatic) for rule in discount.rules}) > 1:
                raise WaiverDiscountValidationError(gettext(
                    'contract_premium_modification'
                    '.msg_automatic_discount_rules'))


class CommercialDiscountModificationRule(
        PremiumModificationRuleMixin, model.CoogView, model.CoogSQL):
    "Commercial Discount Rule"
    __name__ = 'commercial_discount.rule'

    commercial_discount = fields.Many2One(
        'commercial_discount', "Commercial Discount",
        required=True, ondelete='CASCADE', select=True)
    taxes = fields.Many2Many(
        'commercial_discount.rule-account.tax',
        'rule', 'tax', "Rule Taxes")
    coverages = fields.Many2Many(
        'commercial_discount.rule-option.description',
        'rule', 'coverage', "Coverages")

    @classmethod
    def validate(cls, rules):
        pool = Pool()
        CommercialDiscount = pool.get('commercial_discount')

        discounts = set()
        super().validate(rules)
        for rule in rules:
            discounts.add(rule.commercial_discount)
        CommercialDiscount.validate(discounts)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.account_for_modification.required = True
        cls.duration_rule.domain = [('type_', '=', 'discount_duration')]
        cls.duration_rule.states['required'] = Eval('automatic')
        cls.eligibility_rule.domain = [('type_', '=', 'discount_eligibility')]
        cls.eligibility_rule.required = False

    def get_account_for_modification_line(self, line):
        return self.account_for_modification

    def eligible(self, option, modifications):
        if modifications:
            if self.commercial_discount not in modifications:
                return False
        if self.eligibility_rule is not None:
            data = {'date': option.start_date}
            option.init_dict_for_rule_engine(data)
            return self.calculate_eligibility_rule(data)
        else:
            return True

    @classmethod
    def get_modification_line_fields(cls):
        return {
            'type', 'description', 'origin', 'quantity', 'unit', 'unit_price',
            'invoice_type', 'coverage_start', 'coverage_end', 'coverage',
            }

    @classmethod
    def get_modification_line_detail_fields(cls):
        return {
            'rated_entity', 'frequency', 'rate', 'premium', 'loan', 'coverage',
            }

    @property
    def modification_taxes(self):
        return self.taxes

    @property
    def modification(self):
        return self.commercial_discount

    def get_rec_name(self, name):
        return ' %s %.2f %%' % (self.commercial_discount.name, self.rate * 100)


class DiscountRuleTax(model.ConfigurationMixin):
    "Commercial Discount Rule - Taxes"
    __name__ = 'commercial_discount.rule-account.tax'

    rule = fields.Many2One(
        'commercial_discount.rule', "Rule",
        required=True, ondelete='CASCADE')
    tax = fields.Many2One('account.tax', "Tax", required=True,
        ondelete='RESTRICT')


class DiscountRuleOption(model.ConfigurationMixin):
    "Commercial Discount Rule - Contract Option"
    __name__ = 'commercial_discount.rule-option.description'

    rule = fields.Many2One(
        'commercial_discount.rule', "Rule",
        required=True, ondelete='CASCADE')
    coverage = fields.Many2One('offered.option.description', "Coverage",
        required=True, ondelete='RESTRICT')

    @classmethod
    def validate(cls, discount_rule_options):
        pool = Pool()
        Coverage = pool.get('offered.option.description')

        super().validate(discount_rule_options)
        Coverage.check_waiver_discounts()

#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import utils, date, model
from trytond.modules.insurance_product.product import DEF_CUR_DIG, CONFIG_KIND
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot

__all__ = [
    'PricingRule',
    'PriceCalculator',
    'PricingData',
    ]

PRICING_LINE_KINDS = [
    ('base', 'Base Price'),
    ('tax', 'Tax'),
    ('fee', 'Fee')
    ]

PRICING_FREQUENCY = [
    ('yearly', 'Yearly'),
    ('half-yearly', 'Half Yearly'),
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly')
    ]


class PricingData(model.CoopSQL, model.CoopView):
    'Pricing Data'

    __name__ = 'ins_product.pricing_data'

    calculator = fields.Many2One(
        'ins_product.pricing_calculator',
        'Calculator',
        ondelete='CASCADE')

    fixed_amount = fields.Numeric(
        'Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        depends=['kind', 'config_kind'])

    config_kind = fields.Selection(CONFIG_KIND,
        'Conf. kind', required=True)

    rule = fields.Many2One('rule_engine', 'Rule Engine',
        depends=['config_kind', 'kind'])

    kind = fields.Selection(
        PRICING_LINE_KINDS,
        'Line kind',
        required=True)

    code = fields.Char('Code', required=True)

    the_tax = fields.Function(fields.Many2One(
            'coop_account.tax_desc',
            'Tax Descriptor'),
        'get_tax',
        'set_tax')

    the_fee = fields.Function(fields.Many2One(
            'coop_account.fee_desc',
            'Fee Descriptor'),
        'get_fee',
        'set_fee')

    summary = fields.Function(fields.Char('Value',
                    on_change_with=['fixed_amount', 'config_kind', 'rule',
                        'kind', 'the_tax', 'the_fee', 'code']),
        'get_summary')

    def get_tax(self, name):
        if not (self.kind == 'tax' and
                hasattr(self, 'code') and self.code):
            return
        tax = utils.get_those_objects(
            'coop_account.tax_desc',
            [('code', '=', self.code)], 1)
        if tax:
            return tax[0].id

    @classmethod
    def set_tax(cls, calcs, name, value):
        if value:
            try:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('id', '=', value)])
                code = tax.code
                cls.write(calcs, {'code': code})
            except ValueError:
                raise Exception(
                    'Could not found the required Tax Desc')

    def get_fee(self, name):
        if not (self.kind == 'fee' and
                hasattr(self, 'code') and self.code):
            return
        fee = utils.get_those_objects(
            'coop_account.fee_desc',
            [('code', '=', self.code)], 1)
        if fee:
            return fee[0].id

    @classmethod
    def set_fee(cls, calcs, name, value):
        if value:
            try:
                fee, = utils.get_those_objects(
                    'coop_account.fee_desc',
                    [('id', '=', value)])
                code = fee.code
                cls.write(calcs, {'code': code})
            except ValueError:
                raise Exception(
                    'Could not found the required Fee desc')

    @classmethod
    def create(cls, values):
        values = values.copy()
        if 'the_tax' in values and values['the_tax']:
            try:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('id', '=', values['the_tax'])])
                values['code'] = tax.code
            except ValueError:
                raise Exception(
                    'Could not found the required Tax Desc')
        elif 'the_fee' in values and values['the_fee']:
            try:
                fee, = utils.get_those_objects(
                    'coop_account.fee_desc',
                    [('id', '=', values['the_fee'])])
                values['code'] = fee.code
            except ValueError:
                raise Exception(
                    'Could not found the required Fee desc')
        super(PricingData, cls).create(values)

    @staticmethod
    def default_kind():
        return 'base'

    @staticmethod
    def default_config_kind():
        return 'simple'

    def calculate_tax(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def calculate_fee(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def calculate_value(self, args):
        errors = []
        kind = self.kind
        if self.kind == 'tax':
            amount = self.calculate_tax(args)
        elif self.kind == 'fee':
            amount = self.calculate_fee(args)
        elif self.config_kind == 'simple':
            amount = self.fixed_amount
        elif self.config_kind == 'rule' and self.rule:
            res, mess, errs = self.rule.compute(args)
            amount, errors = res, mess + errs
        code = self.code
        name = kind + ' - ' + code
        final_res = PricingResultLine(amount, name)
        final_res.update_details({(kind, code): amount})
        return final_res, errors

    @classmethod
    def get_summary(cls, pricings, name=None, with_label=False, at_date=None,
                    lang=None):
        res = {}
        for pricing in pricings:
            res[pricing.id] = ''
            if pricing.kind == 'tax' and pricing.the_tax:
                res[pricing.id] = pricing.the_tax.rec_name
            elif pricing.kind == 'fee' and pricing.the_fee:
                res[pricing.id] = pricing.the_fee.rec_name
            else:
                if pricing.config_kind == 'rule' and pricing.rule:
                    res[pricing.id] = pricing.rule.rec_name
                elif pricing.config_kind == 'simple':
                    res[pricing.id] = str(pricing.fixed_amount)
        return res

    def get_rec_name(self, name=None):
        return self.get_summary([self])[self.id]

    def on_change_with_summary(self, name=None):
        return self.get_summary([self])[self.id]


class PriceCalculator(model.CoopSQL, model.CoopView):
    'Price Calculator'

    __name__ = 'ins_product.pricing_calculator'

    data = fields.One2Many(
        'ins_product.pricing_data',
        'calculator',
        'Price Components',
        )

    key = fields.Selection(
        [('price', 'Subscriber Price'),
        ('sub_price', 'Sub Elem Price')],
        'Key')

    rule = fields.Many2One(
        'ins_product.pricing_rule',
        'Pricing Rule',
        ondelete='CASCADE')

    simple = fields.Boolean('Basic Combination')

    combine = fields.Many2One(
        'rule_engine',
        'Combining Rule',
        states={
            'invisible': Bool(Eval('simple')),
            'required': ~Bool(Eval('simple'))})

    def calculate_price(self, args):
        result = PricingResultLine()
        errors = []
        for data in self.data:
            res, errs = data.calculate_value(args)
            result += res
            errors += errs
        if not errors and not self.simple and \
                hasattr(self, 'combine') and self.combine:
            new_args = copy.copy(args)
            new_args['price_details'] = result.details
            final_details = {}
            for key in result.details.iterkeys():
                final_details[key] = 0
            new_args['final_details'] = final_details
            res, mess, errs = self.combine.compute(new_args)
            errors += mess + errs
            result = PricingResultLine(value=res)
            result.details = {}
            result.update_details(new_args['final_details'])
        elif not errs and self.simple:
            result.value = 0
            sorted = dict([(key, []) for key, _ in PRICING_LINE_KINDS])
            result.desc = []
            for key, value in result.details.iteritems():
                sorted[key[0]].append((key[1], value))
            for the_code, value in sorted['base']:
                result.value += value
            total_fee = 0
            for the_code, value in sorted['fee']:
                fee, = utils.get_those_objects(
                    'coop_account.fee_desc',
                    [('code', '=', the_code)], 1)
                fee_vers = fee.get_version_at_date(args['date'])
                amount = fee_vers.apply_fee(result.value)
                total_fee += amount
                result.details[('fee', the_code)] = amount
            result.value += total_fee
            total_tax = 0
            for the_code, value in sorted['tax']:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('code', '=', the_code)], 1)
                tax_vers = tax.get_version_at_date(args['date'])
                amount = tax_vers.apply_tax(result.value)
                total_tax += amount
                result.details[('tax', the_code)] = amount
            # result.value += total_tax
        result.create_descs_from_details()
        return result, errors

    def get_rec_name(self, name):
        return 'Price Calculator'

    @staticmethod
    def default_simple():
        return True

#Not working for the moment
#    @staticmethod
#    def default_data():
#        return utils.create_inst_with_default_val(
#            Pool().get('ins_product.pricing_calculator'), 'data')


class PricingRule(model.CoopSQL, BusinessRuleRoot):
    'Pricing Rule'

    __name__ = 'ins_product.pricing_rule'

    price_kind = fields.Selection(
        [
            ('subscriber', 'Subscriber'),
            ('cov_element', 'Covered Elements')
        ],
        'Price based on',
        states={'required': Eval('config_kind') == 'rule'})

    calculators = fields.One2Many(
        'ins_product.pricing_calculator',
        'rule',
        'Calculators')

    price = fields.Function(fields.Many2One(
            'ins_product.pricing_calculator',
            'Price Calculator'),
        'get_calculator')

    sub_price = fields.Function(fields.Many2One(
            'ins_product.pricing_calculator',
            'Price Calculator'),
        'get_calculator')

    frequency = fields.Selection(
        PRICING_FREQUENCY,
        'Rate Frequency',
        required=True)

    basic_price = fields.Function(
        fields.Numeric(
            'Amount',
            digits=(16,
                Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
            ),
        'get_basic_price',
        'set_basic_price')

    basic_tax = fields.Function(
        fields.Many2One(
            'coop_account.tax_desc',
            'Tax'),
        'get_basic_tax',
        'set_basic_tax')

    @staticmethod
    def default_config_kind():
        return 'simple'

    @classmethod
    def set_basic_price(cls, prices, name, value):
        if value:
            Calc = Pool().get('ins_product.pricing_calculator')
            Data = Pool().get('ins_product.pricing_data')
            for price in prices:
                if len(price.calculators) == 1:
                    the_calc = price.calculators[0]
                    Data.delete(
                        [data for data in the_calc.data
                            if data.kind == 'base'])
                else:
                    if len(price.calculators) > 1:
                        Calc.delete(price.calculators)
                    the_calc = Calc()
                    the_calc.key = 'price'
                    the_calc.data = []
                if the_calc.id:
                    the_calc.write([the_calc],
                        {'data': [(
                            'create', {
                                'fixed_amount': value,
                                'kind': 'base',
                                'code': 'PP'})]})
                else:
                    price.write([price], {
                        'calculators': [(
                            'create', {
                                'key': 'price',
                                'data': [(
                                    'create', {
                                        'fixed_amount': value,
                                        'code': 'PP',
                                        'kind': 'base'})]})]})

    @classmethod
    def set_basic_tax(cls, prices, name, value):
        if value:
            try:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('id', '=', value)])
            except ValueError:
                raise Exception(
                    'Could not found a Tax Desc with code %s' % value)
            Calc = Pool().get('ins_product.pricing_calculator')
            Data = Pool().get('ins_product.pricing_data')
            for price in prices:
                if len(price.calculators) == 1:
                    the_calc = price.calculators[0]
                    Data.delete(
                        [data for data in the_calc.data
                            if data.kind == 'tax'])
                else:
                    if len(price.calculators) > 1:
                        Calc.delete(price.calculators)
                    the_calc = Calc()
                    the_calc.key = 'price'
                    the_calc.data = []
                if the_calc.id:
                    the_calc.write([the_calc],
                        {'data': [(
                            'create', {
                                'kind': 'tax',
                                'code': tax.code})]})
                else:
                    price.write([price], {
                        'calculators': [(
                            'create', {
                                'key': 'price',
                                'data': [(
                                    'create', {
                                        'code': tax.code,
                                        'kind': 'tax'})]})]})

    def get_basic_price(self, name):
        if not self.config_kind == 'simple':
            return 0
        calcs = [elem for elem in self.calculators if elem.key == 'price']
        if not calcs or len(calcs) > 1:
            return 0
        calc = calcs[0]
        datas = [data for data in calc.data if data.kind == 'base']
        if not datas or len(datas) > 1:
            return 0
        return datas[0].fixed_amount

    def get_basic_tax(self, name):
        if not self.config_kind == 'simple':
            return
        calcs = [elem for elem in self.calculators if elem.key == 'price']
        if not calcs or len(calcs) > 1:
            return
        calc = calcs[0]
        datas = [data for data in calc.data if data.kind == 'tax']
        if not datas or len(datas) > 1:
            return
        tax = utils.get_those_objects(
            'coop_account.tax_desc',
            [('code', '=', datas[0].code)], 1)
        if tax:
            return tax[0].id

    def get_calculator(self, name):
        if hasattr(self, 'calculators') and self.calculators:
            for elem in self.calculators:
                if elem.key == name:
                    return utils.WithAbstract.serialize_field(elem)
        return None

    def give_me_price(self, args):
        if self.price:
            result, errors = self.price.calculate_price(args)
        else:
            result, errors = (PricingResultLine(value=0), [])

        return result, errors

    def give_me_sub_elem_price(self, args):
        if self.sub_price:
            result, errors = self.sub_price.calculate_price(args)
        else:
            result, errors = (PricingResultLine(value=0), [])

        return result, errors

    def give_me_frequency(self, args):
        if hasattr(self, 'frequency') and self.frequency:
            return self.frequency
        return None

    def give_me_frequency_days(self, args):
        if not 'date' in args:
            return (None, ['A base date must be provided !'])
        the_date = args['date']
        return date.number_of_days_between(
            the_date,
            utils.add_frequency(self.frequency, the_date))

    @staticmethod
    def default_price_kind():
        return 'subscriber'

    @staticmethod
    def default_frequency():
        return 'yearly'

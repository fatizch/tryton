# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.cache import Cache
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields, coog_date, coog_string
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.currency_cog import ModelCurrency

from trytond.modules.coog_core.coog_date import FREQUENCY_CONVERSION_TABLE

__all__ = [
    'Benefit',
    'BenefitProduct',
    'BenefitPaymentJournal',
    'BenefitRule',
    ]

INDEMNIFICATION_KIND = [
    ('capital', 'Capital'),
    ('period', 'Period'),
    ('annuity', 'Annuity'),
    ]
INDEMNIFICATION_DETAIL_KIND = [
    ('deductible', 'Deductible'),
    ('benefit', 'Benefit'),
    ]
ANNUITY_FREQUENCIES = [
    ('', ''),
    ('yearly', 'Yearly'),
    ('half_yearly', 'Half-yearly'),
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly'),
    ]


class Benefit(metaclass=PoolMeta):
    __name__ = 'benefit'

    indemnification_kind = fields.Selection(INDEMNIFICATION_KIND,
        'Indemnification Kind', sort=False, required=True)
    indemnification_kind_string = indemnification_kind.translated(
        'indemnification_kind')
    benefit_rules = fields.One2Many('benefit.rule', 'benefit', 'Benefit Rules',
        delete_missing=True)
    automatic_period_calculation = fields.Boolean(
        'Automatic Period Calculation',
        help='Periods will be automatically calculated reusing data from'
        'previous period.',
        states={'invisible': Eval('indemnification_kind') != 'period'},
        depends=['indemnification_kind'])
    products = fields.Many2Many('benefit-product', 'benefit', 'product',
        'Products')
    waiting_account = fields.Function(fields.Many2One(
            'account.account', 'Waiting Account'),
        'getter_waiting_account')
    payment_journals = fields.Many2Many('benefit-account.payment.journal',
        'benefit', 'payment_journal', 'Payment Journals', help='The payment '
        'journals defined here will be pickable when creating a new '
        'indemnification period on a delivered service for this benefit')

    _indemnification_tax_date_config_cache = Cache(
        'indemnification_tax_date_config')

    @classmethod
    def tax_date_is_indemnification_date(cls):
        cached = cls._indemnification_tax_date_config_cache.get(1, -1)
        if cached != -1:
            return cached
        claim_config = Pool().get('claim.configuration').get_singleton()
        value = claim_config.tax_at_indemnification_date
        cls._indemnification_tax_date_config_cache.set(1, value)
        return value

    @classmethod
    def validate(cls, benefits):
        super(Benefit, cls).validate(benefits)
        with model.error_manager():
            for benefit in benefits:
                accounts = list(
                    set(benefit.get_benefit_accounts()))
                if len(accounts) > 1:
                    cls.append_functional_error('different_product_accounts',
                        {'benefit': benefit.rec_name})

    def has_automatic_period_calculation(self):
        return self.automatic_period_calculation and \
            self.indemnification_kind == 'period'

    def calculate_benefit(self, args):
        if not self.benefit_rules:
            return
        return self.benefit_rules[0].calculate(args)

    def calculate_deductible(self, args):
        if not self.benefit_rules:
            return
        return self.benefit_rules[0].do_calculate_deductible_rule(args).result

    def getter_waiting_account(self, name):
        accounts = self.get_benefit_accounts()
        if accounts:
            return accounts[0]

    def get_benefit_accounts(self):
        return list({x.account_expense_used for x in self.products
                if x.account_expense_used})

    @staticmethod
    def default_indemnification_kind():
        return 'capital'


class BenefitProduct(model.CoogSQL):
    'Benefit Product relation'

    __name__ = 'benefit-product'

    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        ondelete='RESTRICT')


class BenefitPaymentJournal(model.CoogSQL):
    'Benefit Payment Journal relation'

    __name__ = 'benefit-account.payment.journal'

    benefit = fields.Many2One('benefit', 'Benefit', required=True,
        ondelete='CASCADE', select=True)
    payment_journal = fields.Many2One('account.payment.journal', 'Product',
        required=True, ondelete='CASCADE')


class BenefitRule(
        get_rule_mixin('indemnification_rule', 'Indemnification Rule'),
        get_rule_mixin('deductible_rule', 'Deductible Rule'),
        get_rule_mixin('revaluation_rule', 'Revaluation Rule'),
        model.CoogSQL, model.CoogView, ModelCurrency):
    'Benefit Rule'

    __name__ = 'benefit.rule'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE',
        required=True, select=True)
    annuity_frequency = fields.Selection(ANNUITY_FREQUENCIES,
        'Annuity Frequency',
            states={
                'invisible': ~Eval('requires_frequency'),
                'required': Bool(Eval('requires_frequency', False))
                },
        depends=['requires_frequency', 'benefit'])
    requires_frequency = fields.Function(
        fields.Boolean('Frequency Required', depends=['benefit']),
        'get_requires_frequency')

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        cls._error_messages.update({
                'msg_beneficiary_share': 'Share for current beneficiary : '
                '%(share)s %%',
                'msg_final_result': 'Total after share : %(amount).2f',
                'no_indemnification_rule': 'No indemnification rule defined',
                'period_description': 'Indemnification computed with forced '
                'base amount %(forced_amount)s\nIndemnification amount is'
                ' %(forced_amount)s * %(nb_of_unit)s = %(amount)s\n',
                'capital_description': 'Capital forced amount '
                '%(forced_amount)s\n',
                'annuity_general_description': 'Annuities generated with forced'
                ' base amount %(forced_amount)s on a %(frequency)s frequency'
                '\nTherefore, annual annuity amount is '
                '%(annual_forced_amount)s\n',
                'annuity_description': 'The prorata for this period is '
                '%(prorata)s / %(ratio)s = %(prorata_on_ratio)s\nThe '
                'amount per day is %(annual_forced_amount)s / %(ratio)s = '
                '%(amount_per_unit)s \nThe annuity amount is '
                '%(amount_per_unit)s * %(prorata)s = %(annuity_amount)s \n',
                'invalid_detail_deductible_rule': 'Detail %(detail_key) does '
                'not exist in configuration for deductible rules',
                })
        cls.indemnification_rule.domain = [('type_', '=', 'benefit')]
        cls.deductible_rule.domain = [('type_', '=', 'benefit_deductible')]
        cls.revaluation_rule.domain = [('type_', '=', 'benefit_revaluation')]

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module)
        # Migrate from 1.6 : rename 'rule' to 'indemnification_rule'
        if handler.column_exist('rule'):
            handler.column_rename('rule', 'indemnification_rule')
            handler.column_rename('rule_extra_data',
                'indemnification_rule_extra_data')
        super(BenefitRule, cls).__register__(module)

    def get_rec_name(self, name):
        if self.indemnification_rule:
            return self.indemnification_rule.rec_name
        return self.raise_user_error('no_indemnification_rule',
            raise_exception=False)

    @fields.depends('benefit', 'requires_frequency')
    def on_change_benefit(self):
        if self.benefit is None:
            self.requires_frequency = False
        else:
            self.requires_frequency = (self.benefit.indemnification_kind ==
                'annuity')

    def get_requires_frequency(self, name):
        if not self.benefit:
            return False
        return self.benefit.indemnification_kind == 'annuity'

    def get_coverage_amount(self, args):
        if 'option' in args and 'covered_person' in args:
            return args['option'].get_coverage_amount(args['covered_person'])

    @classmethod
    def calculation_dates(cls, indemnification, start_date, end_date):
        res = set()
        for service in indemnification.service.loss.services:
            if service == indemnification.service:
                continue
            for indemn in service.indemnifications:
                for detail in indemn.details:
                    if (detail.start_date > start_date and
                            detail.start_date < end_date):
                        res.add(detail.start_date)
        return res

    @classmethod
    def clean_benefits(cls, benefits):
        benefits = sorted(benefits, key=lambda x: x['start_date'])
        cleaned = []
        for period in benefits:
            if not cleaned or not cls.same_indemnification_line(cleaned[-1],
                    period):
                cleaned.append(period)
            else:
                cls.merge_indemnification_line(cleaned[-1], period)
        return cleaned

    @classmethod
    def same_indemnification_line(cls, line1, line2):
        for fname in ('amount_per_unit', 'unit', 'description',
                'extra_details'):
            if line1.get(fname, None) != line2.get(fname, None):
                return False
        if (line1['end_date'] - line2['start_date']).days != 1:
            return False
        return True

    @classmethod
    def merge_indemnification_line(cls, base, duplicate):
        base['end_date'] = duplicate['end_date']
        base['nb_unit'] += duplicate['nb_unit']
        base['amount'] = base['amount_per_unit'] * base['nb_unit']

    def calculate(self, args):
        res = []
        loss = args['loss']
        indemnification = args['indemnification']
        delivered = args['service']
        deductible_result = self.do_calculate_deductible_rule(args)
        deductible_end_date = (deductible_result.result
            if deductible_result else None)
        deductible_infos = (deductible_result.result_details
            if deductible_result else {})
        previous_date = None
        args['limit_date'] = None
        if deductible_end_date:
            # create deductible if deductible rule is defined
            if args['start_date'] <= deductible_end_date:
                end_period = min(args['end_date'], deductible_end_date)
                description = deductible_infos.pop('description', '')
                details = {}
                if deductible_infos:
                    DetailsConfiguration = Pool().get(
                        'extra_details.configuration')
                    keys = DetailsConfiguration.get_extra_details_fields(
                        'claim.indemnification.detail')
                    for key, value in deductible_infos.items():
                        if key not in keys:
                            self.raise_user_error(
                                'invalid_detail_deductible_rule', {
                                    'detail_key': key,
                                    })
                        details[key] = value
                res.append({
                        'kind': 'deductible',
                        'start_date': args['start_date'],
                        'end_date': end_period,
                        'nb_of_unit':
                        (end_period - args['start_date']).days + 1,
                        'unit': 'day',
                        'amount': 0,
                        'base_amount': 0,
                        'amount_per_unit': 0,
                        'description': description,
                        'extra_details': details,
                        })
                if args['end_date'] <= deductible_end_date:
                    return res
                else:
                    previous_date = deductible_end_date + relativedelta(days=1)
        if not previous_date:
            previous_date = indemnification.start_date
        dates = {extra_data.date or loss.start_date
            for extra_data in delivered.extra_datas
            if (indemnification.start_date <
                (extra_data.date or loss.start_date) <
                indemnification.end_date)}
        # Add pivot periods
        dates |= self.calculation_dates(indemnification, previous_date,
            args['end_date'])
        all_benefits = []

        must_revaluate = self.must_revaluate()
        for start_date, end_date in coog_date.calculate_periods_from_dates(
                list(dates), previous_date, args['end_date']):
            new_args = args.copy()
            new_args['indemnification_full_start'] = indemnification.start_date
            new_args['indemnification_full_end'] = indemnification.end_date
            new_args['date'] = start_date
            new_args['indemnification_detail_start_date'] = start_date
            new_args['indemnification_detail_end_date'] = end_date
            if indemnification.forced_base_amount is not None:
                benefits = self.get_forced_amount_benefits(indemnification)
            else:
                benefits = self.do_calculate_indemnification_rule(new_args)
            new_args['indemnification_periods'] = benefits
            if must_revaluate:
                for benefit in benefits:
                    reval_args = new_args.copy()
                    reval_args['indemnification_detail_start_date'] = \
                        benefit['start_date']
                    reval_args['indemnification_detail_end_date'] = \
                        benefit['end_date']
                    reval_args.update(benefit)
                    reval_benefits = self.do_calculate_revaluation_rule(
                        reval_args) or []
                    for reval_benefit in reval_benefits:
                        tmp_benefit = benefit.copy()
                        tmp_benefit.update(reval_benefit)
                        extra_details_orig = benefit.get('extra_details', {})
                        if 'extra_details' in tmp_benefit:
                            for key, value in list(extra_details_orig.items()):
                                if key not in tmp_benefit['extra_details']:
                                    tmp_benefit['extra_details'][key] = \
                                        value
                        else:
                            tmp_benefit['extra_details'] = extra_details_orig
                        all_benefits.append(tmp_benefit)
            else:
                all_benefits.extend(benefits)
        for benefit in all_benefits:
            benefit['kind'] = 'benefit'
        all_benefits = self.clean_benefits(all_benefits)
        res.extend(all_benefits)
        return res

    def do_calculate_indemnification_rule(self, args):
        result = self.calculate_indemnification_rule(args, raise_errors=True)
        if (not args['indemnification'].share or
                args['indemnification'].share == 1):
            return result
        for elem in result:
            for key in ('amount', 'base_amount', 'amount_per_unit'):
                elem[key] = (args['indemnification'].share *
                    elem.get(key, 0)).quantize(elem.get(key, 0))
            elem['description'] += '\n\n' + self.raise_user_error(
                'msg_beneficiary_share', {
                    'share': args['indemnification'].share * 100},
                raise_exception=False).encode('utf-8')
            elem['description'] += '\n\n' + self.raise_user_error(
                'msg_final_result', {'amount': elem.get('amount')},
                raise_exception=False).encode('utf-8')
        return result

    def get_forced_amount_benefits(self, indemnification):
        res = []
        start_date = indemnification.start_date
        end_date = indemnification.end_date
        forced_base_amount = indemnification.forced_base_amount
        str_forced_base_amount = coog_string.format_number('%.2f',
            forced_base_amount)
        description = ''

        if self.benefit.indemnification_kind == 'period':
            nb_of_unit = (end_date - start_date).days + 1
            amount = forced_base_amount * nb_of_unit

            str_nb_of_unit = coog_string.format_number('%.2f', nb_of_unit)
            str_amount = coog_string.format_number('%.2f', amount)

            description += self.raise_user_error('period_description', {
                    'forced_amount': str_forced_base_amount,
                    'nb_of_unit': str_nb_of_unit,
                    'amount': str_amount
                    },
                raise_exception=False)

            res.append({
                    'start_date': start_date,
                    'end_date': end_date,
                    'nb_of_unit': nb_of_unit,
                    'unit': 'day',
                    'amount': amount,
                    'base_amount': forced_base_amount,
                    'amount_per_unit': forced_base_amount,
                    'description': description,
                    'forced_base_amount': forced_base_amount,
                    'limit_date': None,
                    'extra_details': {}
                    })
        elif self.benefit.indemnification_kind == 'capital':
            nb_of_unit = 1
            end_date = None

            description += self.raise_user_error('capital_description', {
                    'forced_amount': str_forced_base_amount
                    }, raise_exception=False)

            res.append({
                    'start_date': start_date,
                    'end_date': end_date,
                    'nb_of_unit': nb_of_unit,
                    'amount': forced_base_amount,
                    'base_amount': forced_base_amount,
                    'amount_per_unit': forced_base_amount,
                    'forced_base_amount': forced_base_amount,
                    'description': description
                    })
        elif self.benefit.indemnification_kind == 'annuity':
            frequency = indemnification.service.annuity_frequency
            annual_forced_base_amount = forced_base_amount * 12 / \
                FREQUENCY_CONVERSION_TABLE[frequency]

            str_annual_forced_amount = coog_string.format_number('%.2f',
                annual_forced_base_amount)
            description += self.raise_user_error('annuity_general_description',
                {
                    'forced_amount': str_forced_base_amount,
                    'frequency': frequency,
                    'annual_forced_amount': str_annual_forced_amount
                }, raise_exception=False)

            periods = indemnification.service.calculate_annuity_periods(
                start_date, end_date)
            rounding_factor = Decimal(1) / 10 ** indemnification.currency_digits
            res = self.get_ltd_periods(periods, annual_forced_base_amount,
                frequency, description, rounding_factor, forced_base_amount)
        return res

    def get_ltd_periods(self, periods, annual_forced_base_amount, frequency,
            description, rounding_factor, forced_base_amount):
        description_copy = description
        res = []
        for start_date, end_date, full_period, prorata, unit in periods:
            description = description_copy
            ratio = 365
            if unit == 'day':
                amount_per_unit = annual_forced_base_amount / ratio
            else:
                amount_per_unit = annual_forced_base_amount / 12
            annuity_amount = amount_per_unit * prorata

            rounded_annuity_amount = (annuity_amount / rounding_factor
                ).quantize(Decimal('1.'), rounding=ROUND_HALF_UP
                ) * rounding_factor
            rounded_amount_per_unit = (amount_per_unit / rounding_factor
                ).quantize(Decimal('1.'), rounding=ROUND_HALF_UP
                ) * rounding_factor

            str_prorata = coog_string.format_number('%.2f', prorata)
            str_ratio = coog_string.format_number('%.2f', ratio)
            str_prorata_on_ratio = coog_string.format_number('%.2f',
                prorata / Decimal(ratio))
            str_annual_forced_amount = coog_string.format_number('%.2f',
                annual_forced_base_amount)
            str_amount_per_unit = coog_string.format_number('%.2f',
                amount_per_unit)
            str_annuity_amount = coog_string.format_number('%.2f',
                annuity_amount)

            description += self.raise_user_error('annuity_description', {
                    'prorata': str_prorata,
                    'ratio': str_ratio,
                    'prorata_on_ratio': str_prorata_on_ratio,
                    'annual_forced_amount': str_annual_forced_amount,
                    'amount_per_unit': str_amount_per_unit,
                    'annuity_amount': str_annuity_amount
                    }, raise_exception=False)

            res.append({
                    'start_date': start_date,
                    'end_date': end_date,
                    'nb_of_unit': prorata if not full_period else 1,
                    'unit': unit,
                    'amount': rounded_annuity_amount,
                    'base_amount': rounded_amount_per_unit,
                    'amount_per_unit': rounded_amount_per_unit,
                    'description': description,
                    'forced_base_amount': forced_base_amount,
                    'extra_details': {}
                    })
        return res

    def do_calculate_deductible_rule(self, args):
        return self.calculate_deductible_rule(args, return_full=True)

    def do_calculate_revaluation_rule(self, args):
        return self.calculate_revaluation_rule(args)

    def must_revaluate(self):
        if Transaction().context.get('force_no_revaluation', False):
            return False
        return self.revaluation_rule is not None

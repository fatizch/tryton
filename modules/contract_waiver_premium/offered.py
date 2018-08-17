# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql import Table, Literal
from decimal import Decimal

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
from trytond.cache import Cache

from trytond.modules.coog_core import fields, model, utils
from trytond.modules.rule_engine import get_rule_mixin


__all__ = [
    'Product',
    'OptionDescription',
    'WaiverPremiumRule',
    'WaiverPremiumRuleTaxRelation',
    ]


class Product:
    __metaclass__ = PoolMeta
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


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    with_waiver_of_premium = fields.Function(
        fields.Boolean('With Waiver Of Premium'),
        'get_with_waiver_of_premium')
    waiver_premium_rule = fields.One2Many(
        'waiver_premium.rule', 'coverage',
        'Waiver Of Premium Rule', delete_missing=True, size=1)

    def get_with_waiver_of_premium(self, name):
        return bool(self.waiver_premium_rule)

    def init_waiver_line(self, line, waiver_option):
        return self.waiver_premium_rule[0].init_waiver_line(line, waiver_option)


class WaiverPremiumRule(get_rule_mixin('duration_rule', 'Duration Rule',
            extra_string='Duration Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Waiver of Premium Rule'

    _func_key = 'func_key'
    __name__ = 'waiver_premium.rule'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        required=True, ondelete='CASCADE', select=True)
    automatic = fields.Boolean('Automatic')
    rate = fields.Numeric('Rate', digits=(16, 4),
        domain=[('rate', '>', 0), ('rate', '<=', 1)])
    taxes = fields.Many2Many('waiver_premium.rule-account.tax',
        'waiver_rule', 'tax', 'Taxes')
    account_for_waiver = fields.Many2One('account.account',
        'Account to compensate the Waiver', ondelete='RESTRICT',
        domain=[('kind', 'not in', ['payable', 'receivable'])])
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

    @classmethod
    def __setup__(cls):
        super(WaiverPremiumRule, cls).__setup__()
        cls.duration_rule.domain = [('type_', '=', 'waiver_duration')]
        cls.duration_rule.help = \
            'Returns a list containing the start and the end date'
        cls.duration_rule.states['required'] = Bool(Eval('automatic'))
        cls.duration_rule.depends += ['automatic']
        cls._error_messages.update({
                'waiver_line': 'Waiver of Premium',
                })

    @staticmethod
    def default_rate():
        return Decimal(1)

    @staticmethod
    def default_invoice_line_period_behaviour():
        return 'total_overlap'

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

    def get_account_for_waiver_line(self, line):
        if self.account_for_waiver:
            return self.account_for_waiver
        else:
            return self.coverage.get_account_for_billing(line)

    def init_waiver_line(self, line, waiver_option):
        InvoiceLine = Pool().get('account.invoice.line')
        line.taxes = [x.id for x in self.taxes]
        line.account = self.get_account_for_waiver_line(line)
        waiver_start = waiver_option.start_date or datetime.date.min
        waiver_end = waiver_option.end_date or datetime.date.max
        fully_exonerated = (waiver_start <= line.coverage_start
            and waiver_end >= line.coverage_end)
        if self.invoice_line_period_behaviour == 'proportion' \
                and not fully_exonerated:
            assert line.details
            premium = getattr(line.details[0], 'premium', None)
            if not premium:
                return line
            line.unit_price = -1 * utils.get_prorated_amount_on_period(
                max(line.coverage_start, waiver_start),
                min(line.coverage_end, waiver_end),
                frequency=premium.frequency, value=premium.amount,
                sync_date=premium.main_contract.start_date,
                interval_start=premium.start,
                proportion=True, recursion=True
                ) * self.rate
            line.unit_price = line.unit_price.quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])
        else:
            line.unit_price *= -1 * self.rate
        line.description += ' - ' + self.raise_user_error(
            'waiver_line', raise_exception=False)
        return line


class WaiverPremiumRuleTaxRelation(model.CoogSQL):
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

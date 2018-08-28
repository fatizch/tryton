# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.model import Unique, ModelView

from trytond.modules.coog_core import fields, model, utils
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'Claim',
    'ClaimLoss',
    'ClaimService',
    'Salary',
    'NetCalculationRule',
    'NetCalculationRuleExtraData',
    'NetCalculationRuleFixExtraData',
    ]


class NetCalculationRuleFixExtraData(model.CoogSQL):
    'Net Calculation Rule - Extra Data'
    __metaclass__ = PoolMeta
    __name__ = 'net_calculation_rule-fix_extra_data'

    calculation_rule = fields.Many2One('claim.net_calculation_rule',
        'Calculation Rule', required=True, ondelete='CASCADE')
    extra_data = fields.Many2One('extra_data', 'Contributions',
        required=True, ondelete='CASCADE')


class NetCalculationRuleExtraData(model.CoogSQL):
    'Net Calculation Rule - Extra Data'
    __metaclass__ = PoolMeta
    __name__ = 'net_calculation_rule-extra_data'

    calculation_rule = fields.Many2One('claim.net_calculation_rule',
        'Calculation Rule', required=True, ondelete='CASCADE')
    extra_data = fields.Many2One('extra_data', 'Contributions',
        required=True, ondelete='CASCADE')


class NetCalculationRule(model.CoogSQL, model.CoogView,
        get_rule_mixin('rule', 'Rule')):
    'Net Calculation Rule'
    __metaclass__ = PoolMeta
    __name__ = 'claim.net_calculation_rule'
    _func_key = 'name'

    name = fields.Char('Name', required=True)
    contributions = fields.Many2Many('net_calculation_rule-extra_data',
        'calculation_rule', 'extra_data', 'Contributions',
        domain=[('kind', '=', 'salary')], required=True)
    fixed_contributions = fields.Many2Many(
        'net_calculation_rule-fix_extra_data', 'calculation_rule',
        'extra_data', 'Fixed Contributions',
        domain=[('kind', '=', 'salary')])

    @classmethod
    def __setup__(cls):
        super(NetCalculationRule, cls).__setup__()
        cls.rule.domain = [
            ('type_', '=', 'benefit_net_salary_calculation')]
        cls.rule.states.update({'required': True})
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.name), 'The name must be unique!'),
            ]


class Salary(model.CoogSQL, model.CoogView, ModelCurrency):
    'Claim Salary'
    __metaclass__ = PoolMeta
    __name__ = 'claim.salary'

    delivered_service = fields.Many2One('claim.service', 'Delivered Service',
        ondelete='CASCADE', required=True, select=True)
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    gross_salary = fields.Numeric('Gross Salary',
        digits=(16, Eval('currency_digits', 2)),
        states={'readonly': Bool(Eval('is_readonly'))},
        depends=['currency_digits', 'is_readonly'])
    net_salary = fields.Numeric('Net Salary',
        digits=(16, Eval('currency_digits', 2)),
        states={'readonly': Bool(Eval('is_readonly'))},
        depends=['currency_digits', 'is_readonly'])
    salary_bonus = fields.Numeric('Salary Bonus',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    net_salary_bonus = fields.Numeric('Net Salary Bonus',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    ta_contributions = fields.Dict('extra_data', 'TA Contributions',
        domain=[('kind', '=', 'salary')])
    tb_contributions = fields.Dict('extra_data', 'TB Contributions',
        domain=[('kind', '=', 'salary')])
    tc_contributions = fields.Dict('extra_data', 'TC Contributions',
        domain=[('kind', '=', 'salary')])
    net_limit_mode = fields.Function(
        fields.Boolean('Net Limit Mode'),
        'get_net_limit_mode')
    fixed_contributions = fields.Dict('extra_data', 'Fixed Contributions',
        domain=[('kind', '=', 'salary')])
    is_readonly = fields.Function(
        fields.Boolean('Is Readonly'),
        'get_is_readonly')
    color = fields.Function(
        fields.Char('Color', depends=['is_readonly']),
        'get_color')
    has_contributions = fields.Function(
        fields.Boolean('Has Contributions'),
        'get_has_contributions')

    @classmethod
    def __setup__(cls):
        super(Salary, cls).__setup__()
        cls._order = [('from_date', 'DESC')]

    @classmethod
    def view_attributes(cls):
        return super(Salary, cls).view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black'))]

    def get_color(self, name):
        if self.is_readonly:
            return 'grey'
        return 'black'

    def get_is_readonly(self, name):
        periods = self.delivered_service.calculate_salaries_period_dates()
        for period in periods:
            if period[0] == self.from_date and period[1] == self.to_date:
                return not period[2]
        return True

    def get_currency(self):
        if self.delivered_service:
            return self.delivered_service.currency

    @classmethod
    def update_contributions_table(cls, contributions, tables, key):
        ExtraData = Pool().get('extra_data')
        for k, v in contributions.items():
            data_def = ExtraData._extra_data_struct(k)
            tables[k]['extra_data'] = data_def['id']
            tables[k][key] = v

    def get_rates_per_range(self, fixed=False, net_salary_rule=None):
        ExtraData = Pool().get('extra_data')
        delivered = self.delivered_service
        net_calculation_rule = net_salary_rule or \
            delivered.benefit.benefit_rules[0]. \
            option_benefit_at_date(delivered.option,
                delivered.loss.start_date).net_calculation_rule
        extra_datas = net_calculation_rule.contributions if not fixed \
            else net_calculation_rule.fixed_contributions
        tables = defaultdict(lambda: {
                'ta': 0,
                'tb': 0,
                'tc': 0,
                'fixed_amount': 0,
                'extra_data': None,
                })
        if not fixed:
            self.update_contributions_table(self.ta_contributions,
                tables, 'ta')
            self.update_contributions_table(self.tb_contributions,
                tables, 'tb')
            self.update_contributions_table(self.tc_contributions,
                tables, 'tc')
        else:
            self.update_contributions_table(self.fixed_contributions, tables,
                'fixed_amount')

        missing_rates = [x for x in extra_datas if x.id not in
            [v['extra_data'] for k, v in tables.items()]]
        for missing in missing_rates:
            tables[missing.name] = {
                'ta': 0,
                'tb': 0,
                'tc': 0,
                'fixed_amount': 0,
                'extra_data': missing.id,
                }
        return sorted(tables.values(),
            key=lambda x: ExtraData(x['extra_data']).name)

    @fields.depends('ta_contributions', 'tb_contributions', 'tc_contributions',
        'fixed_contributions')
    def get_has_contributions(self, name=None):
        return self.gross_salary and (self.ta_contributions or
                self.tb_contributions or self.tc_contributions or
                self.fixed_contributions)

    @fields.depends('delivered_service')
    def get_net_limit_mode(self, name=None):
        delivered_service = self.delivered_service
        if not delivered_service:
            return False
        return delivered_service.benefit.benefit_rules[0]. \
            option_benefit_at_date(delivered_service.option,
                delivered_service.loss.start_date).net_salary_mode

    def get_range(self, range_name=None, fixed=False, codes_list=None):
        if fixed:
            extra_data = getattr(self, 'fixed_contributions', None)
        elif range_name:
            extra_data = getattr(self, 't%s_contributions' %
                range_name.lower(), None)
        if codes_list:
            extra_data = {k: extra_data[k] for k in codes_list
                if k in extra_data}
        if not extra_data:
            return None
        # If fixed: fixed values must be already slicked by the number
        # of salaries
        return sum(extra_data.values())

    def calculate_net_salary(self):
        context = {'date': utils.today()}
        delivered_service = self.delivered_service
        rule = delivered_service.benefit.benefit_rules[0]. \
            option_benefit_at_date(delivered_service.option,
                delivered_service.loss.start_date).net_calculation_rule.rule
        delivered_service.init_dict_for_rule_engine(context)
        context['curr_salary'] = self
        self.net_salary = rule.execute(context).result
        self.save()


class ClaimLoss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss'

    @classmethod
    @model.CoogView.button
    def activate(cls, losses):
        super(ClaimLoss, cls).activate(losses)
        for loss in losses:
            for service in loss.services:
                service.init_salaries()

    def get_salary_reference_date(self):
        if self.loss_desc_kind == 'ltd':
            return self.initial_std_start_date
        if self.is_a_relapse:
            return self.relapse_initial_loss.start_date
        return self.start_date


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    salary = fields.One2Many('claim.salary', 'delivered_service', 'Salary',
        order=[('from_date', 'ASC')], delete_missing=True, readonly=True)
    gross_salary = fields.Function(
        fields.Numeric('Gross Salary', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_field')
    net_salary = fields.Function(
        fields.Numeric('Gross Salary', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_field')
    salary_bonus = fields.Function(
        fields.Numeric('Gross Salary Bonus',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_field')
    net_salary_bonus = fields.Function(
        fields.Numeric('Net Salary Bonus',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_field')
    salary_mode = fields.Function(
        fields.Char('Salary Mode'),
        'get_salary_mode')
    ta_gross_salary = fields.Function(
        fields.Numeric('TA Gross Salary',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_range')
    tb_gross_salary = fields.Function(
        fields.Numeric('TB Gross Salary',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_range')
    tc_gross_salary = fields.Function(
        fields.Numeric('TC Gross Salary',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_range')

    def get_salary_reference_date(self):
        Covered = Pool().get('contract.covered_element')
        reference = self.loss.get_salary_reference_date()
        covered = self.get_theoretical_covered_element(None)
        if covered:
            return min(reference,
                Covered(covered).contract_exit_date or datetime.date.max)
        return reference

    def calculate_salaries_period_dates(self):
        if self.salary_mode in ('last_12_months', 'last_12_months_last_year'):
            nb_iteration = 12
        elif self.salary_mode in ('last_3_months', 'last_3_months_last_year'):
            nb_iteration = 3
        elif self.salary_mode in ('last_year', 'last_month',
                'last_month_last_year'):
            nb_iteration = 1
        elif self.salary_mode == 'last_4_quarters':
            nb_iteration = 4
        else:
            return []

        salary_date = self.get_salary_reference_date()
        if self.salary_mode in ('last_12_months', 'last_3_months',
                'last_month', 'last_year'):
            reference_date = salary_date
        elif self.salary_mode in ('last_12_months_last_year',
                'last_3_months_last_year', 'last_month_last_year'):
            reference_date = datetime.date(salary_date.year - 1, 12, 31)
        elif self.salary_mode == 'last_4_quarters':
            reference_date = salary_date + relativedelta(day=1,
                    month=((salary_date.month - 1) // 3) * 3 + 1)
        else:
            return []

        res = []
        end_month = datetime.date(reference_date.year, reference_date.month,
            1) - relativedelta(days=1)
        for i in range(0, 12):
            if (self.salary_mode in ('last_4_quarters', 'last_year')
                    and nb_iteration <= i):
                break
            if self.salary_mode == 'last_year':
                start_month = end_month + relativedelta(days=1,
                    years=-1)
            elif self.salary_mode == 'last_4_quarters':
                start_month = end_month + relativedelta(days=1) - \
                    relativedelta(months=3)
            else:
                start_month = datetime.date(end_month.year, end_month.month, 1)
            res.append((start_month, end_month, nb_iteration > i))
            end_month = start_month - relativedelta(days=1)
        return res

    def init_salaries(self):
        Salary = Pool().get('claim.salary')
        if self.loss.is_a_relapse:
            return

        salaries_period = self.calculate_salaries_period_dates()

        # Use getattr since the salary field not be set yet
        per_date = {x.from_date: x for x in getattr(self, 'salary', [])}

        salaries = []
        for from_date, to_date, required in salaries_period:
            if from_date in per_date:
                salaries.append(per_date[from_date])
            else:
                salaries.append(Salary(from_date=from_date,
                        to_date=to_date))
        self.salary = salaries
        self.save()

    def get_salary_mode(self, name=None):
        return self.benefit.benefit_rules[0].option_benefit_at_date(
            self.option, self.loss.start_date).salary_mode

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        self.salary_mode = self.get_salary_mode()
        self.init_salaries()

    def calculate_basic_salary(self, salaries_def, current_salary=None,
            args=None):
        """
            This method returns the TA, TB, TC range based on basic salary
            Basic salary is always an annual salary. The calculation is the sum
            of salaries according salary_mode definition.
            Bonus salaries is always the sum of all bonus during the year. No
            proration required
            If revaluation is defined on basic salary and if args is
            defined basic salary will be revaluated
        """
        pool = Pool()

        TableCell = pool.get('table.cell')
        Table = pool.get('table')

        def calculate_salary_range(salary, pmss):
            salary_range = {'TA': 0, 'TB': 0, 'TC': 0}
            salary_range['TA'] = min(pmss, salary)
            if salary > pmss:
                salary_range['TB'] = min(3 * pmss, salary - pmss)
                if salary > 4 * pmss:
                    salary_range['TC'] = min(4 * pmss, salary - 4 * pmss)
            return salary_range

        pmss_table, = Table.search([('code', '=', 'pmss')])
        salary_range = {'TA': 0, 'TB': 0, 'TC': 0}
        salaries = self.claim.delivered_services[0].salary \
            if not current_salary else [current_salary]
        salary_mode = self.claim.delivered_services[0].salary_mode
        pmss = Decimal(0)
        salary_to_use = Decimal(0)
        bonus = Decimal(0)

        periods = \
            self.claim.delivered_services[0].calculate_salaries_period_dates()
        if not periods:
            return salary_range
        min_date = min([period[0] for period in periods if period[2]])
        max_date = max([period[1] for period in periods if period[2]])
        sum_prorata = Decimal(0)

        for cur_salary in salaries:
            in_period = True
            if (cur_salary.from_date > max_date or
                    cur_salary.to_date < min_date):
                in_period = False
            # calculate prorata in order to calculate the salary as it was a
            # full month
            if salary_mode != 'last_year':
                begin_date = datetime.date(cur_salary.to_date.year,
                    cur_salary.to_date.month, 1)
            else:
                begin_date = cur_salary.to_date + relativedelta(days=1,
                    years=-1)
            prorata = ((cur_salary.to_date - cur_salary.from_date).days + 1) / \
                Decimal((cur_salary.to_date - begin_date).days + 1)
            for salary_def in salaries_def:
                if 'bonus' in salary_def:
                    # bonus are added only one time at the end
                    # and are not prorated
                    bonus += getattr(cur_salary, salary_def, 0) or 0
                elif in_period:
                    salary_to_add = \
                        (getattr(cur_salary, salary_def, 0) or 0)
                    if salary_to_add:
                        if salary_mode != 'last_year':
                            pmss += TableCell.get(pmss_table,
                                cur_salary.from_date) * prorata
                        sum_prorata += prorata
                        salary_to_use += salary_to_add
            if salary_mode == 'last_year':
                for i in range(0, 12):
                    pmss += TableCell.get(pmss_table, cur_salary.from_date +
                        relativedelta(months=i)) * prorata

        # Calculate monthly salary
        if salary_mode != 'last_year' and not current_salary and \
                sum_prorata:
            salary_to_use *= 12 / sum_prorata
            pmss *= 12 / sum_prorata
        salary_to_use += bonus

        pmss = pmss.quantize(Decimal(1) / 10 ** self.currency_digits)
        salary_to_use = salary_to_use.quantize(Decimal(1) /
            10 ** self.currency_digits)

        salary_to_use = self.apply_revaluation_if_needed(salary_to_use, args)

        year_range = calculate_salary_range(salary_to_use, pmss)
        salary_range['TA'] = year_range['TA']
        salary_range['TB'] = year_range['TB']
        salary_range['TC'] = year_range['TC']

        return salary_range

    def apply_revaluation_if_needed(self, salary, args):
        if (not args or
                not self.benefit.benefit_rules or
                not self.benefit.benefit_rules[
                    0].process_revaluation_on_basic_salary(self)):
            return salary
        cur_args = args.copy()
        cur_args['base_amount'] = salary
        cur_args['description'] = ''
        res = self.benefit.benefit_rules[0].calculate_revaluation_rule(cur_args)
        return res[0]['amount_per_unit']

    @classmethod
    def get_salary_range(cls, services, names):
        ta_gross_salary = {s.id: Decimal('0.0') for s in services}
        tb_gross_salary = {s.id: Decimal('0.0') for s in services}
        tc_gross_salary = {s.id: Decimal('0.0') for s in services}
        for service in services:
            salary_range = service.calculate_basic_salary(
                ['gross_salary', 'salary_bonus'])
            ta_gross_salary[service.id] = salary_range['TA']
            tb_gross_salary[service.id] = salary_range['TB']
            tc_gross_salary[service.id] = salary_range['TC']
        result = {
            'ta_gross_salary': ta_gross_salary,
            'tb_gross_salary': tb_gross_salary,
            'tc_gross_salary': tc_gross_salary
            }
        return {key: result[key] for key in names}

    def get_salary_field(self, name):
        res = 0
        for cur_salary in self.salary:
            res += (getattr(cur_salary, name, 0) or 0)
        return res


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._buttons.update({
                'launch_salaries_wizard': {},
                })

    @classmethod
    @ModelView.button_action('claim_salary_fr.salaries_wizard')
    def launch_salaries_wizard(cls, claims):
        pass

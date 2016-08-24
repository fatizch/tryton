# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Or
from trytond.model import Unique

from trytond.modules.cog_utils import fields, model, utils
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'ClaimService',
    'Salary',
    'ExtraDatasDisplayers',
    'IndemnificationDefinition',
    'CreateIndemnification',
    'FillExtraData',
    'NetCalculationRule',
    'NetCalculationRuleExtraData',
    'NetCalculationRuleFixExtraData',
    ]


class NetCalculationRuleFixExtraData(model.CoopSQL):
    'Net Calculation Rule - Extra Data'
    __metaclass__ = PoolMeta
    __name__ = 'net_calculation_rule-fix_extra_data'

    calculation_rule = fields.Many2One('claim.net_calculation_rule',
        'Calculation Rule', required=True, ondelete='CASCADE')
    extra_data = fields.Many2One('extra_data', 'Extra Data',
        required=True, ondelete='CASCADE')


class NetCalculationRuleExtraData(model.CoopSQL):
    'Net Calculation Rule - Extra Data'
    __metaclass__ = PoolMeta
    __name__ = 'net_calculation_rule-extra_data'

    calculation_rule = fields.Many2One('claim.net_calculation_rule',
        'Calculation Rule', required=True, ondelete='CASCADE')
    extra_data = fields.Many2One('extra_data', 'Extra Data',
        required=True, ondelete='CASCADE')


class NetCalculationRule(model.CoopSQL, model.CoopView,
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
        domain=[('kind', '=', 'salary')], required=True)

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


class Salary(model.CoopSQL, model.CoopView):
    'Claim Salary'
    __metaclass__ = PoolMeta
    __name__ = 'claim.salary'

    delivered_service = fields.Many2One('claim.service', 'Delivered Service',
        ondelete='CASCADE', required=True, select=True)
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    gross_salary = fields.Numeric('Gross Salary',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    net_salary = fields.Numeric('Net Salary',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    salary_bonus = fields.Numeric('Salary Bonus',
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
    ta_fixed_contributions = fields.Dict('extra_data', 'TA Fixed Contributions',
        domain=[('kind', '=', 'salary')])
    tb_fixed_contributions = fields.Dict('extra_data', 'TB Fixed Contributions',
        domain=[('kind', '=', 'salary')])
    tc_fixed_contributions = fields.Dict('extra_data', 'TC Fixed Contributions',
        domain=[('kind', '=', 'salary')])

    @classmethod
    def __setup__(cls):
        super(Salary, cls).__setup__()
        cls._order = [('from_date', 'DESC')]
        cls._buttons.update({
                'set_contributions': {
                    'invisible': Or(
                        ~Bool(Eval('gross_salary')),
                        ~Bool(Eval('net_limit_mode')))}
                })

    @classmethod
    @model.CoopView.button_action('claim_salary_fr.act_set_contributions')
    def set_contributions(cls, salaries):
        pass

    @classmethod
    def update_contributions_table(cls, contributions, tables, key):
        ExtraData = Pool().get('extra_data')
        for k, v in contributions.items():
            extra_data = ExtraData._extra_data_cache.get(k, None)
            if not extra_data:
                extra_data = ExtraData.search(
                    [('name', '=', k)], limit=1)[0].id
                ExtraData._extra_data_cache.set(k, extra_data)
            tables[k]['extra_data'] = extra_data
            tables[k][key] = v

    def get_rates_per_range(self, fixed=False):
        delivered = self.delivered_service
        net_calculuation_rule = delivered.benefit.benefit_rules[0]. \
            option_benefit_at_date(delivered.option,
                delivered.loss.start_date).net_calculation_rule
        extra_datas = net_calculuation_rule.contributions if not fixed \
            else net_calculuation_rule.fixed_contributions
        tables = defaultdict(lambda: {
                'ta': 0,
                'tb': 0,
                'tc': 0,
                'ta_fix': 0,
                'tb_fix': 0,
                'tc_fix': 0,
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
            self.update_contributions_table(self.ta_fixed_contributions,
                tables, 'ta_fix')
            self.update_contributions_table(self.tb_fixed_contributions,
                tables, 'tb_fix')
            self.update_contributions_table(self.tc_fixed_contributions,
                tables, 'tc_fix')

        missing_rates = [x for x in extra_datas if x.id not in
            [v['extra_data'] for k, v in tables.items()]]
        for missing in missing_rates:
            tables[missing.name] = {
                'ta': 0,
                'tb': 0,
                'tc': 0,
                'ta_fix': 0,
                'tb_fix': 0,
                'tc_fix': 0,
                'extra_data': missing.id,
                }
        return tables.values()

    @fields.depends('delivered_service')
    def get_net_limit_mode(self, name=None):
        delivered_service = self.delivered_service
        if not delivered_service:
            return False
        return delivered_service.benefit.benefit_rules[0]. \
            option_benefit_at_date(delivered_service.option,
                delivered_service.loss.start_date).net_salary_mode

    def get_range(self, range_name, fixed=False):
        if fixed:
            range_name += '_fixed'
        extra_data = getattr(self, 't%s_contributions' %
            range_name.lower(), None)
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


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    salary = fields.One2Many('claim.salary', 'delivered_service', 'Salary')
    gross_salary = fields.Function(
        fields.Numeric('Gross Salary', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_field')
    net_salary = fields.Function(
        fields.Numeric('Gross Salary', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_field')
    salary_bonus = fields.Function(
        fields.Numeric('Gross Salary', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_salary_field')

    def init_salaries(self):
        Salary = Pool().get('claim.salary')
        if self.loss.is_a_relapse:
            return
        salary_mode = self.benefit.benefit_rules[0]. \
            option_benefit_at_date(self.option,
                self.loss.start_date).salary_mode
        if salary_mode in ('last_12_months', 'last_12_months_last_year'):
            nb_iteration = 12
        elif salary_mode in ('last_3_months', 'last_3_months_last_year'):
            nb_iteration = 3
        elif salary_mode in ('last_month', 'last_month_last_year'):
            nb_iteration = 1

        if salary_mode in ('last_12_months', 'last_3_months', 'last_month'):
            reference_date = self.loss.start_date
        elif salary_mode in ('last_12_months_last_year',
                'last_3_months_last_year', 'last_month_last_year'):
            reference_date = datetime.date(
                self.loss.start_date.year - 1, 12, 31)

        to_save = []
        end_month = datetime.date(reference_date.year, reference_date.month,
            1) - relativedelta(days=1)
        for i in range(0, nb_iteration):
            start_month = datetime.date(end_month.year, end_month.month, 1)
            to_save.append(Salary(from_date=start_month, to_date=end_month,
                delivered_service=self))
            end_month = start_month - relativedelta(days=1)

        # Salary.update_salary_with_existing_info(to_save)
        Salary.save(to_save)

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        self.init_salaries()

    def calculate_basic_salary(self, salaries_def, current_salary=None):
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
        if self.loss.is_a_relapse:
            salaries = self.claim.delivered_services[0].salary \
                if not current_salary else [current_salary]
        else:
            salaries = self.salary if not current_salary else [current_salary]
        for cur_salary in salaries:
            salary_to_use = 0
            for salary_def in salaries_def:
                salary_to_use += getattr(cur_salary, salary_def, 0) or 0
            pmss = TableCell.get(pmss_table, cur_salary.from_date)
            month_range = calculate_salary_range(salary_to_use, pmss)
            salary_range['TA'] += month_range['TA']
            salary_range['TB'] += month_range['TB']
            salary_range['TC'] += month_range['TC']
        salary_mode = self.benefit.benefit_rules[0]. \
            option_benefit_at_date(self.option,
                self.loss.start_date).salary_mode
        for key, value in salary_range.iteritems():
            if salary_mode in ('last_3_months', 'last_3_months_last_year'):
                coefficient = 4
            elif salary_mode == ('last_month', 'last_month_last_year'):
                coefficient = 12
            else:
                coefficient = 1
            salary_range[key] = value * coefficient
        return salary_range

    def get_salary_field(self, name):
        res = 0
        for cur_salary in self.salary:
            res += (getattr(cur_salary, name, 0) or 0)
        return res


class ExtraDatasDisplayers:
    __metaclass__ = PoolMeta
    __name__ = 'claim.extra_datas_displayers'

    salaries = fields.Many2Many('claim.salary', None, None, 'Salaries')


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    salaries = fields.Many2Many('claim.salary', None, None, 'Salaries')


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    def default_definition(self, name):
        pool = Pool()
        Service = pool.get('claim.service')
        res = super(CreateIndemnification, self).default_definition(name)
        service = Service(res['service'])
        res['salaries'] = [s.id for s in service.salary]
        return res

    def transition_calculate(self):
        Salary = Pool().get('claim.salary')
        Salary.save(self.definition.salaries)
        return super(CreateIndemnification, self).transition_calculate()


class FillExtraData:
    __metaclass__ = PoolMeta
    __name__ = 'claim.fill_extra_datas'

    def default_definition(self, name):
        pool = Pool()
        Service = pool.get('claim.service')
        res = super(FillExtraData, self).default_definition(name)
        service = Service(res['service'])
        res['salaries'] = [s.id for s in service.salary]
        return res

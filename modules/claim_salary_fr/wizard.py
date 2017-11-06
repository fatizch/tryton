# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.modules.coog_core import model, fields


__all__ = [
    'StartSetContributions',
    'ContributionsView',
    'StartSetSalaries',
    'SalariesComputation',
    ]


class StartSetSalaries(model.CoogView):
    'Start Set Salaries'
    __name__ = 'claim.start_set_salaries'

    periods = fields.One2Many('claim.salary', None, 'Periods',
        order=[('from_date', 'ASC')], readonly=True)
    net_limit_mode = fields.Boolean('Net Limit Mode')


class ContributionsView(model.CoogView):
    'Contributions View'
    __name__ = 'claim.contributions_view'

    extra_data = fields.Many2One('extra_data', 'Contributions',
        domain=[('kind', '=', 'salary')])
    ta = fields.Numeric('Rate A', digits=(16, 4), required=True)
    tb = fields.Numeric('Rate B', digits=(16, 4), required=True)
    tc = fields.Numeric('Rate C', digits=(16, 4), required=True)
    fixed_amount = fields.Numeric('Amount', digits=(16, 4), required=True)


class StartSetContributions(model.CoogView):
    'Start Set Contributions'
    __metaclass__ = PoolMeta
    __name__ = 'claim.start_set_contributions'

    rates = fields.One2Many('claim.contributions_view', None, 'Rates',
        readonly=True)
    fixed_amounts = fields.One2Many('claim.contributions_view', None,
        'Fixed Amounts', readonly=True)
    rule = fields.Many2One('rule_engine', 'Rule', states={
           'invisible': True})
    periods = fields.One2Many('claim.salary', None, 'Periods',
        order=[('from_date', 'ASC')], readonly=True)


class SalariesComputation(Wizard):
    'Salaries Computation Wizard'
    __name__ = 'claim.salaries_computation'

    start = StateView('claim.start_set_salaries',
        'claim_salary_fr.start_set_salaries_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'process', 'tryton-go-next', default=True)])
    process = StateTransition()
    net_salary = StateView('claim.start_set_contributions',
        'claim_salary_fr.start_set_contributions_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'start', 'tryton-go-previous'),
            Button('Compute net salaries', 'set_contributions',
                'tryton-go-next'),
            Button('Compute and finish', 'compute', 'tryton-go-next',
                default=True)])
    compute = StateTransition()
    set_contributions = StateTransition()

    @classmethod
    def __setup__(cls):
        super(SalariesComputation, cls).__setup__()
        cls._error_messages.update({
                'no_delivered_services': 'No service can be delivered for this'
                ' claim',
                'no_rule': 'No net salary computation rule has been defined',
                'indemnifications': 'This claim has indemnification periods, '
                'you may have to cancel them or recompute if salaries are '
                'modifed'
                })

    def get_rule_service(self):
        assert Transaction().context.get('active_model') == 'claim'
        selected_id = Transaction().context.get('active_id')
        claim = Pool().get('claim')(selected_id)
        services = claim.delivered_services
        if services:
            is_indemnificated = any(x.indemnifications for x in services)
            net_limit_mode = False
            rule = None
            for service in services:
                for benefit_rule in service.benefit.benefit_rules:
                    benefit_at_date = benefit_rule.option_benefit_at_date(
                        service.option, service.loss.start_date)
                    if benefit_at_date.net_salary_mode:
                        net_limit_mode = True
                        rule = benefit_at_date.net_calculation_rule
                        break
                if net_limit_mode:
                    break
            return {
                'is_indemnificated': is_indemnificated,
                'delivered_service': services[0],
                'net_limit_mode': net_limit_mode,
                'rule': rule,
                }
        return None

    def default_start(self, fields):
        delivered = self.get_rule_service()
        if not delivered:
            self.raise_user_error('no_delivered_services')
        if delivered['is_indemnificated']:
            self.raise_user_warning('indemnifications', 'indemnifications')
        net_limit_mode = delivered['net_limit_mode']
        delivered_service = delivered['delivered_service']
        return {
            'periods': [s.id for s in delivered_service.salary],
            'net_limit_mode': net_limit_mode,
            }

    def transition_process(self):
        pool = Pool()
        Salary = pool.get('claim.salary')
        Salary.save(self.start.periods)
        if self.start.net_limit_mode and self.start.periods[0]:
            return 'net_salary'
        else:
            return 'end'

    def default_net_salary(self, fields):
        delivered_rule = self.get_rule_service()
        if not delivered_rule:
            self.raise_user_error('no_delivered_services')
        delivered_service = delivered_rule['delivered_service']
        rule = delivered_rule['rule']
        if not rule:
            self.raise_user_error('no_rule')
        salaries = delivered_service.salary
        return {
            'rule': rule.rule.id,
            'periods': [s.id for s in salaries],
            'rates': salaries[0].get_rates_per_range(
                net_salary_rule=rule),
            'fixed_amounts': salaries[0].get_rates_per_range(fixed=True,
                net_salary_rule=rule)
            }

    def update_salary(self):
        to_calculate = []
        to_empty = []
        for salary in self.net_salary.periods:
            if not salary.gross_salary:
                if salary.net_salary:
                    to_empty.append(salary)
                continue
            for rate in self.net_salary.rates:
                salary.ta_contributions[rate.extra_data.name] = rate.ta
                salary.tb_contributions[rate.extra_data.name] = rate.tb
                salary.tc_contributions[rate.extra_data.name] = rate.tc
            for rate in self.net_salary.fixed_amounts:
                salary.fixed_contributions[rate.extra_data.name] = \
                    rate.fixed_amount
            to_calculate.append(salary)
        for salary in to_calculate:
            salary.ta_contributions = salary.ta_contributions
            salary.tb_contributions = salary.tb_contributions
            salary.tc_contributions = salary.tc_contributions
            salary.fixed_contributions = salary.fixed_contributions
            salary.calculate_net_salary()
        if to_empty:
            Salary = Pool().get('claim.salary')
            Salary.write(to_empty, {'net_salary': None})

    def transition_set_contributions(self):
        self.update_salary()
        return 'net_salary'

    def transition_compute(self):
        self.update_salary()
        return 'end'

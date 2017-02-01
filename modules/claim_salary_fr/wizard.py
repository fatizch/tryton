# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Not, Eval, Bool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.modules.coog_core import model, fields


__all__ = [
    'ComputeNetSalaries',
    'StartSetContributions',
    'ContributionsView',
    ]


class ContributionsView(model.CoogView):
    'Contributions View'
    __name__ = 'claim_salary_fr.contributions_view'

    extra_data = fields.Many2One('extra_data', 'Contributions',
        domain=[('kind', '=', 'salary')])
    ta = fields.Numeric('Rate A', digits=(16, 4), required=True)
    tb = fields.Numeric('Rate B', digits=(16, 4), required=True)
    tc = fields.Numeric('Rate C', digits=(16, 4), required=True)
    fixed_amount = fields.Numeric('Amount', digits=(16, 4), required=True)


class StartSetContributions(model.CoogView):
    'Start Set Contributions'
    __metaclass__ = PoolMeta
    __name__ = 'claim_salary_fr.start_set_contributions'

    rates = fields.One2Many('claim_salary_fr.contributions_view',
        None, 'Rates')
    fixed_amounts = fields.One2Many('claim_salary_fr.contributions_view',
        None, 'Fixed Amounts')
    rule = fields.Many2One('rule_engine', 'Rule', states={
           'invisible': True})
    salary = fields.Many2One('claim.salary', 'Salary', states={
           'invisible': True})
    propagate = fields.Boolean('Propagate on salaries',
        help="Propagate on each salaries with a defined gross salary")
    periods = fields.One2Many('claim.salary', None, 'Periods',
        order=[('from_date', 'ASC')], states={
            'invisible': Not(Bool(Eval('propagate'))),
            })


class ComputeNetSalaries(Wizard):
    'Compute net salaries'
    __metaclass__ = PoolMeta
    __name__ = 'claim_salary_fr.compute_net_salaries'

    start = StateView('claim_salary_fr.start_set_contributions',
        'claim_salary_fr.start_set_contributions_view_form', [
            Button('End', 'end', 'tryton-cancel'),
            Button('Compute net salaries', 'process',
                'tryton-go-next', default=True)])
    process = StateTransition()

    def default_start(self, name):
        pool = Pool()
        selected_id = Transaction().context.get('active_id')
        assert Transaction().context.get('active_model') == 'claim.salary'
        salary = pool.get('claim.salary')(selected_id)
        delivered = salary.delivered_service
        rule = delivered.benefit.benefit_rules[0].option_benefit_at_date(
            delivered.option,
            delivered.loss.start_date).net_calculation_rule.rule

        start_dict = {
            'rule': rule.id,
            'salary': selected_id,
            'propagate': True,
            'periods': [x.id for x in delivered.salary],
            'rates': salary.get_rates_per_range(),
            'fixed_amounts': salary.get_rates_per_range(fixed=True),
            }
        return start_dict

    def transition_process(self):
        to_calculate = []
        if self.start.propagate:
            salaries = self.start.periods
            for salary in salaries:
                if not salary.gross_salary:
                    continue
                for rate in self.start.rates:
                    salary.ta_contributions[rate.extra_data.name] = rate.ta
                    salary.tb_contributions[rate.extra_data.name] = rate.tb
                    salary.tc_contributions[rate.extra_data.name] = rate.tc
                for rate in self.start.fixed_amounts:
                    salary.fixed_contributions[rate.extra_data.name] = \
                        rate.fixed_amount
                to_calculate.append(salary)
        else:
            if not self.start.salary.gross_salary:
                return 'end'
            for rate in self.start.rates:
                self.start.salary.ta_contributions[
                    rate.extra_data.name] = rate.ta
                self.start.salary.tb_contributions[
                    rate.extra_data.name] = rate.tb
                self.start.salary.tc_contributions[
                    rate.extra_data.name] = rate.tc
            for rate in self.start.fixed_amounts:
                self.start.salary.fixed_contributions[rate.extra_data.name] = \
                    rate.fixed_amount
            to_calculate.append(self.start.salary)

        # Needed to save properly the extra datas
        for salary in to_calculate:
            salary.ta_contributions = salary.ta_contributions
            salary.tb_contributions = salary.tb_contributions
            salary.tc_contributions = salary.tc_contributions
            salary.fixed_contributions = salary.fixed_contributions
            salary.calculate_net_salary()
        return 'end'

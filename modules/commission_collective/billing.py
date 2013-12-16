from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'RateNoteLine',
    ]


class RateNoteLine():
    'Rate Note line'

    __name__ = 'billing.premium_rate.form.line'

    def calculate_bill_line(self, work_set):
        super(RateNoteLine, self).calculate_bill_line(work_set)
        if not self.amount or not self.client_amount or self.childs:
            return
        key = (self.rate_line.covered_element,
            self.rate_line.option_.offered.account_for_billing)
        if not key in work_set['lines']:
            return
        line = work_set['lines'][key]
        for comp_option in self.rate_line.option_.commissions:
                values = work_set['coms'][comp_option.com_option.offered.id]
                values['object'] = comp_option.com_option
                values['to_recalculate'] |= False
                values['base'] += self.client_amount
                com = comp_option.calculate_com(self.client_amount, self.rate_line.start_date)[0]
                rounded_com = work_set['currency'].round(com)
                values['amount'] += rounded_com
                line.credit -= rounded_com
                work_set['total_amount'] -= rounded_com

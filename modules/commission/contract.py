from decimal import Decimal
from collections import defaultdict

from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import model, fields, coop_date
from trytond.modules.insurance_product import PricingResultDetail

__all__ = [
    'PriceLineComRelation',
    'PriceLine',
    'Contract',
    ]


class PriceLineComRelation(model.CoopSQL, model.CoopView):
    'Price line to Commission relation'

    __name__ = 'commission.price_line-com-relation'

    price_line = fields.Many2One('billing.price_line', 'Price Line',
        ondelete='CASCADE')
    com_subscribed = fields.Many2One('contract.subscribed_option',
        'Commission Subscribed', ondelete='RESTRICT')
    amount = fields.Numeric('Amount')
    to_recalculate = fields.Boolean('Recalculate at billing')


class PriceLine():
    'Price Line'

    __metaclass__ = PoolMeta
    __name__ = 'billing.price_line'

    com_lines = fields.One2Many('commission.price_line-com-relation',
        'price_line', 'Commission lines')
    estimated_com = fields.Function(
        fields.Numeric('Estimated Commissions'), 'get_estimated_coms')
    estimated_wo_com = fields.Function(
        fields.Numeric('Estimated w/o coms'),
        'get_estimated_wo_com')

    def get_estimated_wo_com(self, name):
        return self.amount - self.estimated_com

    def init_from_result_line(self, line, build_details=False):
        super(PriceLine, self).init_from_result_line(line, build_details)
        if build_details:
            self.build_com_lines(line)

    @classmethod
    def must_create_detail(cls, detail):
        res = super(PriceLine, cls).must_create_detail(detail)
        if not res:
            return res
        if detail.on_object.__name__ == 'commission.compensated_option':
            return False
        return True

    def build_com_lines(self, line):
        ComLine = Pool().get('commission.price_line-com-relation')
        if not (hasattr(self, 'com_lines') and self.com_lines):
            self.com_lines = []
        for com_line in (x for x in line.details if x.on_object and
                x.on_object.__name__ == 'commission.compensated_option'):
            com_relation = ComLine()
            com_relation.com_subscribed = com_line.on_object.com_option
            # Com detail lines store the rate in the amount field. We need
            # to apply it now to avoid taxes and fees
            com_relation.amount = self.amount * com_line.amount
            self.com_lines.append(com_relation)

    def get_estimated_coms(self, field_name):
        res = 0
        for elem in self.com_lines:
            res += elem.amount
        return res

    def get_base_amount_for_billing(self):
        result = super(PriceLine, self).get_base_amount_for_billing()
        for elem in self.com_lines:
            result -= elem.amount
        return result

    def calculate_bill_contribution(self, work_set, period):
        result = super(PriceLine, self).calculate_bill_contribution(work_set,
            period)
        number_of_days = coop_date.number_of_days_between(*period)
        price_line_days = self.get_number_of_days_at_date(period[0])
        convert_factor = number_of_days / Decimal(price_line_days)
        for com_line in self.com_lines:
            values = work_set['coms'][com_line.com_subscribed.offered.id]
            values['object'] = com_line.com_subscribed
            values['to_recalculate'] |= com_line.to_recalculate
            values['amount'] += com_line.amount * convert_factor
            values['base'] += result.credit
        return result


class Contract():
    'Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    def get_protocol_offered(self, kind):
        dist_network = self.get_dist_network()
        if kind != 'commission' or not dist_network:
            return super(Contract, self).get_protocol(kind)
        coverages = [x.offered for x in self.options]
        for comp_plan in [x for x in dist_network.all_com_plans
                if not x.end_date or x.end_date >= self.start_date]:
            compensated_cov = []
            for comp in comp_plan.coverages:
                compensated_cov.extend(comp.coverages)
            if set(coverages).issubset(set(compensated_cov)):
                return comp_plan

    def calculate_price_at_date(self, date):
        prices, errs = super(Contract, self).calculate_price_at_date(date)
        for price in prices:
            target = price.on_object
            if target.__name__ != 'offered.coverage':
                continue
            target = self.get_option_for_coverage_at_date(target, date)
            if not target:
                continue
            for option, rate in target.get_com_options_and_rates_at_date(date):
                # Just store the rate, the amount will be calculted later
                com_line = PricingResultDetail(rate, option)
                price.details.append(com_line)
        return (prices, errs)

    def init_billing_work_set(self):
        res = super(Contract, self).init_billing_work_set()
        res['coms'] = defaultdict(
                lambda: {'amount': 0, 'base': 0, 'to_recalculate': False})
        return res

    def calculate_final_coms(self, work_set):
        for data in work_set['coms'].itervalues():
            account = data['object'].get_account_for_billing()
            line = work_set['lines'][(data['object'].offered, account)]
            line.party = data['object'].current_policy_owner
            line.account = account
            line.second_origin = data['object'].offered
            amount = work_set['currency'].round(data['amount'])
            line.credit += amount
            work_set['total_amount'] += amount

    def calculate_final_taxes_and_fees(self, work_set):
        ht_total = work_set['total_amount']
        super(Contract, self).calculate_final_taxes_and_fees(work_set)
        new_total = work_set['total_amount']
        work_set['total_amount'] = ht_total
        self.calculate_final_coms(work_set)
        work_set['total_amount'] += new_total - ht_total

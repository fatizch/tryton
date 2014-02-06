from decimal import Decimal

from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import model, fields, coop_date

__metaclass__ = PoolMeta
__all__ = [
    'BillingPremiumCommissionOptionRelation',
    'Premium',
    ]


class BillingPremiumCommissionOptionRelation(model.CoopSQL, model.CoopView):
    'Billing Premium-Commission Option Relation'

    __name__ = 'contract.billing.premium-commission.option'

    price_line = fields.Many2One('contract.billing.premium', 'Price Line',
        ondelete='CASCADE')
    com_option = fields.Many2One('contract.option',
        'Commission Subscribed', ondelete='RESTRICT')
    amount = fields.Numeric('Amount')
    to_recalculate = fields.Boolean('Recalculate at billing')


class Premium:
    __name__ = 'contract.billing.premium'

    com_lines = fields.One2Many('contract.billing.premium-commission.option',
        'price_line', 'Commission lines')
    estimated_com = fields.Function(
        fields.Numeric('Estimated Commissions'), 'get_estimated_coms')
    estimated_wo_com = fields.Function(
        fields.Numeric('Estimated w/o coms'),
        'get_estimated_wo_com')

    def get_estimated_wo_com(self, name):
        return self.amount - self.estimated_com

    def init_from_result_line(self, line, build_details=False):
        super(Premium, self).init_from_result_line(line, build_details)
        if build_details:
            self.build_com_lines(line)

    @classmethod
    def must_create_detail(cls, detail):
        res = super(Premium, cls).must_create_detail(detail)
        if not res:
            return res
        if detail.on_object.__name__ == 'contract.option-commission.option':
            return False
        return True

    def build_com_lines(self, line):
        ComLine = Pool().get('contract.billing.premium-commission.option')
        if not (hasattr(self, 'com_lines') and self.com_lines):
            self.com_lines = []
        for com_line in (x for x in line.details if x.on_object and
                x.on_object.__name__ == 'contract.option-commission.option'):
            com_relation = ComLine()
            com_relation.com_option = com_line.on_object.com_option
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
        result = super(Premium, self).get_base_amount_for_billing()
        for elem in self.com_lines:
            result -= elem.amount
        return result

    def calculate_bill_contribution(self, work_set, period):
        result = super(Premium, self).calculate_bill_contribution(work_set,
            period)
        number_of_days = coop_date.number_of_days_between(*period)
        price_line_days = self.get_number_of_days_at_date(*period)
        convert_factor = number_of_days / Decimal(price_line_days)
        for com_line in self.com_lines:
            values = work_set.coms[com_line.com_option.offered.id]
            values['object'] = com_line.com_option
            values['to_recalculate'] |= com_line.to_recalculate
            values['amount'] += com_line.amount * convert_factor
            values['base'] += result.credit
        return result

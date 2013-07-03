from trytond.pyson import Eval, Equal, If
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coop_utils import fields, model, utils


__all__ = [
    'CommissionAgreement',
    'CommissionOption',
    'CompensatedOption',
    ]


class CommissionAgreement():
    'Commission Agreement'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(CommissionAgreement, cls).__setup__()
        utils.update_domain(cls, 'subscriber', [If(
                    Equal(Eval('product_kind'), 'commission'),
                    ('is_broker', '=', True),
                    (),
                    )])
        utils.update_depends(cls, 'subscriber', ['product_kind'])

    def update_management_roles(self):
        super(CommissionAgreement, self).update_management_roles()
        role = self.get_management_role('commission')
        agreement = role.protocol if role else None
        if not agreement:
            return
        for option in self.options:
            option.update_commissions(agreement)


class CommissionOption():
    'Commission Option'

    __name__ = 'contract.subscribed_option'
    __metaclass__ = PoolMeta

    compensated_options = fields.One2Many('commission.compensated_option',
        'com_option', 'Compensated Options',
        states={'invisible': Eval('coverage_kind') != 'commission'},
        context={'from': 'com'})
    commissions = fields.One2Many('commission.compensated_option',
        'subs_option', 'Commissions',
        states={'invisible': Eval('coverage_kind') != 'insurance'},
        context={'from': 'subscribed'})

    def update_commissions(self, agreement):
        CompOption = Pool().get('commission.compensated_option')
        for com_option in agreement.options:
            if not self.offered in com_option.offered.coverages:
                continue
            good_comp_option = None
            for comp_option in self.commissions:
                if comp_option.com_option == com_option:
                    good_comp_option = comp_option
                    break
            if not good_comp_option:
                good_comp_option = CompOption()
                good_comp_option.com_option = com_option
                if not self.commissions:
                    self.commissions = []
                self.commissions = list(self.commissions)
                self.commissions.append(good_comp_option)
            good_comp_option.start_date = self.start_date
            self.save()

    def get_com_options_and_rates_at_date(self, at_date):
        for commission in self.commissions:
            if commission.start_date > at_date:
                continue
            if commission.end_date and commission.end_date < at_date:
                continue
            com_rate = commission.get_com_rate()
            if not com_rate:
                continue
            yield((commission, com_rate[0]))

    def get_account_for_billing(self):
        if self.coverage_kind != 'commission':
            return self.offered.get_account_for_billing()
        return self.current_policy_owner.account_payable


class CompensatedOption(model.CoopSQL, model.CoopView):
    'Compensated Option'

    __name__ = 'commission.compensated_option'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    com_option = fields.Many2One('contract.subscribed_option',
        'Commission Option', domain=[('coverage_kind', '=', 'commission')],
        ondelete='RESTRICT')
    subs_option = fields.Many2One('contract.subscribed_option',
        'Subscribed Coverage', domain=[('coverage_kind', '=', 'insurance')],
        ondelete='CASCADE')
    use_specific_rate = fields.Boolean('Specific Rate')
    rate = fields.Numeric('Rate', states={
            'invisible': ~Eval('use_specific_rate'),
            'required': ~~Eval('use_specific_rate'),
            })
    com_amount = fields.Function(
        fields.Numeric('Com Amount'),
        'get_com_amount')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')

    def get_rec_name(self, name):
        option = None
        if Transaction().context.get('from') == 'com':
            option = self.subs_option
        else:
            option = self.com_option
        if not option:
            return ''
        return '%s - %s (%s)' % (
            option.current_policy_owner.rec_name,
            option.contract.contract_number
            if option.contract.contract_number else '',
            option.rec_name,
            )

    def get_all_complementary_data(self, at_date):
        res = {}
        res.update(self.com_option.get_all_complementary_data(at_date))
        res.update(self.subs_option.get_all_complementary_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        args['comp_option'] = self
        self.com_option.init_dict_for_rule_engine(args)

    def get_com_rate(self):
        cur_dict = {'date': self.start_date}
        self.init_dict_for_rule_engine(cur_dict)
        res = self.com_option.offered.get_result('commission', cur_dict)
        return res

    def get_com_amount(self, name):
        com_rate = self.get_com_rate()
        if not com_rate or not com_rate[0] or not hasattr(
                com_rate[0], 'result'):
            return 0
        for price_line in self.subs_option.contract.prices:
            if price_line.on_object == self.subs_option.offered:
                return com_rate[0].result * price_line.amount

    def get_currency(self):
        return self.com_option.currency

    def on_change_with_com_lines(self, name=None):
        return [{}]

    @classmethod
    def set_void(cls, instances):
        pass

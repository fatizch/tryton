from trytond.pyson import Eval, Equal, If
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coop_utils import fields, model, utils
from trytond.modules.coop_currency import ModelCurrency

from .plan import COMMISSION_KIND

__all__ = [
    'CommissionAgreement',
    'CommissionOption',
    'CompensatedOption',
    ]


class CommissionAgreement():
    'Commission Agreement'

    __name__ = 'contract'
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
        for com_kind in [x[0] for x in COMMISSION_KIND]:
            role = self.get_management_role(com_kind)
            agreement = role.protocol if role else None
            if not agreement:
                continue
            for option in self.options:
                option.update_commissions(agreement)


class CommissionOption():
    'Commission Option'

    __name__ = 'contract.option'
    __metaclass__ = PoolMeta

    compensated_options = fields.One2Many('contract.option-commission.option',
        'com_option', 'Compensated Options',
        states={'invisible': Eval('coverage_kind') != 'commission'},
        context={'from': 'com'})
    commissions = fields.One2Many('contract.option-commission.option',
        'subs_option', 'Commissions',
        states={'invisible': Eval('coverage_kind') != 'insurance'},
        context={'from': 'subscribed'})

    def update_commissions(self, agreement):
        CompOption = Pool().get('contract.option-commission.option')
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
            com_rate = commission.get_com_rate(at_date)
            if not com_rate:
                continue
            yield((commission, com_rate))

    def get_account_for_billing(self):
        if self.coverage_kind != 'commission':
            return self.offered.get_account_for_billing()
        return self.current_policy_owner.account_payable


class CompensatedOption(model.CoopSQL, model.CoopView, ModelCurrency):
    'Compensated Option'

    __name__ = 'contract.option-commission.option'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    com_option = fields.Many2One('contract.option',
        'Commission Option', domain=[('coverage_kind', '=', 'commission')],
        ondelete='RESTRICT')
    subs_option = fields.Many2One('contract.option',
        'Subscribed Coverage', domain=[('coverage_kind', '=', 'insurance')],
        ondelete='CASCADE')
    use_specific_rate = fields.Boolean('Specific Rate')
    rate = fields.Numeric('Rate', digits=(16, 4), states={
            'invisible': ~Eval('use_specific_rate'),
            'required': ~~Eval('use_specific_rate'),
            })
    com_amount = fields.Function(
        fields.Numeric('Com Amount'),
        'get_com_amount')

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

    def get_com_rate(self, at_date=None):
        if not at_date:
            at_date = utils.today()
        if not(at_date >= self.start_date
                and (not self.end_date or at_date <= self.end_date)):
            return 0, None
        cur_dict = {'date': at_date}
        self.init_dict_for_rule_engine(cur_dict)
        rer = self.com_option.offered.get_result('commission', cur_dict)
        if hasattr(rer, 'errors') and not rer.errors:
            return rer.result
        else:
            return 0

    def calculate_com(self, base_amount, at_date):
        #TODO : deal with non linear com
        com_rate = self.get_com_rate(at_date)
        return com_rate * base_amount, com_rate

    def get_com_amount(self, name):
        for price_line in self.subs_option.contract.prices:
            if price_line.on_object == self.subs_option.offered:
                return self.calculate_com(price_line.amount).result

    def get_currency(self):
        return self.com_option.currency

    def on_change_with_com_lines(self, name=None):
        return [{}]

    @classmethod
    def set_void(cls, instances):
        pass

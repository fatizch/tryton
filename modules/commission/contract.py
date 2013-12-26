from collections import defaultdict

from trytond.pyson import Eval, Equal, If
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coop_utils import fields, model, utils
from trytond.modules.coop_currency import ModelCurrency
from trytond.modules.offered import PricingResultDetail

from .offered import COMMISSION_KIND

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'Option',
    'OptionCommissionOptionRelation',
    'ContractAgreementRelation',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        utils.update_domain(cls, 'subscriber', [If(
                    Equal(Eval('product_kind'), 'commission'),
                    ('is_broker', '=', True),
                    (),
                    )])
        utils.update_depends(cls, 'subscriber', ['product_kind'])

    def update_management_roles(self):
        super(Contract, self).update_management_roles()
        for com_kind in [x[0] for x in COMMISSION_KIND]:
            role = self.get_management_role(com_kind)
            agreement = role.protocol if role else None
            if not agreement:
                continue
            for option in self.options:
                option.update_commissions(agreement)

    def get_protocol_offered(self, kind):
        dist_network = self.get_dist_network()
        if kind not in ['business_provider', 'management'] or not dist_network:
            return super(Contract, self).get_protocol(kind)
        coverages = [x.offered for x in self.options]
        for comp_plan in [x for x in dist_network.all_com_plans
                if x.commission_kind == kind
                and (not x.end_date or x.end_date >= self.start_date)]:
            compensated_cov = []
            for comp in comp_plan.coverages:
                compensated_cov.extend(comp.coverages)
            if set(coverages).issubset(set(compensated_cov)):
                return comp_plan

    def calculate_price_at_date(self, date):
        prices, errs = super(Contract, self).calculate_price_at_date(date)
        for price in prices:
            target = price.on_object
            if target.__name__ != 'offered.option.description':
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


class Option:
    __name__ = 'contract.option'

    compensated_options = fields.One2Many('contract.option-commission.option',
        'com_option', 'Option-Commission Option Relations',
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


class OptionCommissionOptionRelation(model.CoopSQL, model.CoopView,
        ModelCurrency):
    'Option-Commission Option Relation'

    __name__ = 'contract.option-commission.option'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    com_option = fields.Many2One('contract.option', 'Commission Option',
        domain=[('coverage_kind', '=', 'commission')], ondelete='RESTRICT')
    subs_option = fields.Many2One('contract.option', 'Subscribed Coverage',
        domain=[('coverage_kind', '=', 'insurance')], ondelete='CASCADE')
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


class ContractAgreementRelation:
    __name__ = 'contract-agreement'

    @classmethod
    def get_possible_management_role_kind(cls):
        res = super(ContractAgreementRelation, cls).get_possible_management_role_kind()
        res.extend(COMMISSION_KIND)
        return list(set(res))

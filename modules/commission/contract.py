from collections import defaultdict

from trytond.pyson import Eval, Equal, If, Bool
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, utils
from trytond.modules.currency_cog import ModelCurrency

from .offered import COMMISSION_KIND

__metaclass__ = PoolMeta
__all__ = [
    'OptionCommissionOptionRelation',
    'Contract',
    'Option',
    'ContractAgreementRelation',
    'ContractInvoice',
    'CommissionInvoice',
    'Invoice',
    'Premium',
    'PremiumCommission',
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

    def update_agreements(self):
        super(Contract, self).update_agreements()
        for com_kind in [x[0] for x in COMMISSION_KIND]:
            role = self.get_agreement(com_kind)
            agreement = role.protocol if role else None
            if not agreement:
                continue
            for option in self.options:
                option.update_com_options(agreement)
            for covered_element in self.covered_elements:
                for option in covered_element.options:
                    option.update_com_options(agreement)

    def get_protocol_offered(self, kind):
        dist_network = self.get_dist_network()
        if kind not in ['business_provider', 'management'] or not dist_network:
            return super(Contract, self).get_protocol(kind)
        coverages = [x.coverage for x in self.options]
        for comp_plan in [x for x in dist_network.all_com_plans
                if x.commission_kind == kind
                and (not x.end_date or x.end_date >= self.start_date)]:
            compensated_cov = []
            for comp in comp_plan.coverages:
                compensated_cov.extend(comp.coverages)
            if set(coverages).issubset(set(compensated_cov)):
                return comp_plan

    @classmethod
    def get_option(cls, base_instance):
        if base_instance.__name__ == 'contract.option':
            return base_instance
        elif base_instance.__name__ == 'loan.share':
            return base_instance.option
        elif base_instance.__name__ == 'contract.extra_premium':
            return base_instance.option
        return None

    def calculate_price_at_date(self, date):
        prices, errs = super(Contract, self).calculate_price_at_date(date)
        for price in prices:
            target = self.get_option(price['target'])
            if target is None:
                price['commissions'] = []
                continue
            price['commissions'] = []
            for option, rate in target.get_com_options_and_rates_at_date(date):
                # Just store the rate, the amount will be calculted later
                price['commissions'].append({
                        'rate': rate,
                        'option': option,
                        })
        return (prices, errs)

    def get_publishing_context(self, cur_context):
        result = super(Contract, self).get_publishing_context(cur_context)
        result['BusinessProviders'] = [x.party for x in self.agreements
            if x.kind == 'business_provider']
        result['BusinessManagers'] = [x.party.id for x in self.agreements
            if x.kind == 'management']
        return result

    @classmethod
    def invoice_periods(cls, periods):
        contract_invoices = super(Contract, cls).invoice_periods(periods)
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        Journal = pool.get('account.journal')
        CommissionInvoice = pool.get('contract.invoice.commission')
        journals = Journal.search([
                ('type', '=', 'expense'),
                ], limit=1)
        journal = journals[0] if journals else None
        invoices = defaultdict(list)
        for contract_invoice in contract_invoices:
            lines = defaultdict(list)
            for line in contract_invoice.invoice.lines:
                if not line.origin:
                    continue
                if not line.origin.__name__ == 'contract.premium':
                    continue
                if not line.origin.commissions:
                    continue
                for com_line in line.origin.commissions:
                    lines[com_line.party].append(InvoiceLine(
                            type='line',
                            description=com_line.get_description(),
                            origin=line.origin,
                            quantity=1,
                            unit=None,
                            unit_price=contract_invoice.invoice.currency.round(
                                com_line.rate * line.unit_price),
                            taxes=[],
                            invoice_type='in_invoice',
                            account=com_line.com_option.account_for_billing,
                            contract_insurance_start= \
                                line.contract_insurance_start,
                            contract_insurance_end=line.contract_insurance_end,
                            ))
            if not lines:
                continue
            for party, com_lines in lines.iteritems():
                com_invoice = Invoice(
                    company=contract_invoice.invoice.company,
                    type='in_invoice',
                    journal=journal,
                    party=party,
                    invoice_address=party.addresses[0],
                    currency=contract_invoice.invoice.currency,
                    account=party.account_payable,
                    payment_term=contract_invoice.invoice.payment_term,
                    )
                com_invoice.lines = com_lines
                invoices[contract_invoice].append(com_invoice)
        if not invoices:
            return contract_invoices
        com_invoices = Invoice.create([i._save_values
                for j in invoices.itervalues()
                for i in j])
        for com_invoice, old_invoice in zip(com_invoices,
                [i for j in invoices.itervalues() for i in j]):
            old_invoice.id = com_invoice.id
        contract_com_invoices = []
        for contract_invoice, com_invoices in invoices.iteritems():
            for invoice in com_invoices:
                contract_com_invoices.append(CommissionInvoice(
                        contract_invoice=contract_invoice.id,
                        com_invoice=invoice.id))
        if contract_com_invoices:
            CommissionInvoice.create([i._save_values
                    for i in contract_com_invoices])
        return invoices

    def before_activate(self, contract_dict=None):
        if not contract_dict:
            return
        if not 'agreements' in contract_dict:
            return
        pool = Pool()
        Agreement = pool.get('contract-agreement')
        Party = pool.get('party.party')
        self.agreements = []
        for agreement_dict in contract_dict['agreements']:
            agreement = Agreement()
            agreement.kind = agreement_dict.get('kind',
                agreement.default_kind())
            if ('broker' in agreement_dict
                    and 'code' in agreement_dict['broker']):
                parties = Party.search([
                        ('broker_role.reference', '=',
                            agreement_dict['broker']['code']),
                    ], limit=1, order=[])
                if not parties:
                    #TODO raise error
                    continue
                agreement.party = parties[0]
            self.agreements.append(agreement)
        self.update_agreements()
        super(Contract, self).before_activate(contract_dict)


class Option:
    __name__ = 'contract.option'

    options = fields.One2Many('contract.option-commission.option',
        'com_option', 'Option-Commission Option Relations',
        states={'invisible': Eval('coverage_kind') != 'commission'},
        context={'from': 'com'})
    com_options = fields.One2Many('contract.option-commission.option',
        'option', 'Commissions',
        states={'invisible': Eval('coverage_kind') != 'insurance'},
        context={'from': 'subscribed'})

    def update_com_options(self, agreement):
        CompOption = Pool().get('contract.option-commission.option')
        for com_option in agreement.options:
            if not self.coverage in com_option.coverage.coverages:
                continue
            good_comp_option = None
            for comp_option in getattr(self, 'com_options', []):
                if comp_option.com_option == com_option:
                    good_comp_option = comp_option
                    break
            if not good_comp_option:
                good_comp_option = CompOption()
                good_comp_option.com_option = com_option
                if not getattr(self, 'com_options', []):
                    self.com_options = []
                self.com_options = list(self.com_options)
                self.com_options.append(good_comp_option)
            good_comp_option.start_date = self.start_date
            self.save()

    def get_com_options_and_rates_at_date(self, at_date):
        for commission in self.com_options:
            com_rate = commission.get_com_rate(at_date)
            if not com_rate:
                continue
            yield((commission, com_rate))

    def get_account_for_billing(self):
        if self.coverage_kind != 'commission':
            return self.coverage.get_account_for_billing()
        return self.current_policy_owner.account_payable

    def get_all_extra_data(self, at_date):
        if self.coverage_kind != 'commission':
            return super(Option, self).get_all_extra_data(at_date)
        return {}


class OptionCommissionOptionRelation(model.CoopSQL, model.CoopView,
        ModelCurrency):
    'Option-Commission Option Relation'

    __name__ = 'contract.option-commission.option'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    com_option = fields.Many2One('contract.option', 'Commission Option',
        domain=[('coverage_kind', '=', 'commission')], ondelete='RESTRICT')
    option = fields.Many2One('contract.option', 'Subscribed Option',
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
            option = self.option
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

    def get_all_extra_data(self, at_date):
        res = {}
        res.update(self.com_option.get_all_extra_data(at_date))
        res.update(self.option.get_all_extra_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        args['comp_option'] = self
        args['appliable_conditions_date'] = self.start_date
        self.com_option.init_dict_for_rule_engine(args)
        self.option.init_dict_for_rule_engine(args)

    def get_com_rate(self, at_date=None):
        if not at_date:
            at_date = utils.today()
        if not(at_date >= self.start_date
                and (not self.end_date or at_date <= self.end_date)):
            return 0, None
        cur_dict = {'date': at_date}
        self.init_dict_for_rule_engine(cur_dict)
        rer = self.com_option.coverage.get_result('commission', cur_dict)
        if hasattr(rer, 'errors') and not rer.errors:
            return rer.result
        else:
            return 0

    def calculate_com(self, base_amount, at_date):
        #TODO : deal with non linear com
        com_rate = self.get_com_rate(at_date)
        return com_rate * base_amount, com_rate

    def get_com_amount(self, name):
        for price_line in self.option.contract.prices:
            if price_line.on_object == self.option.coverage:
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
    def get_possible_agreement_kind(cls):
        res = super(ContractAgreementRelation,
            cls).get_possible_agreement_kind()
        res.extend(COMMISSION_KIND)
        return list(set(res))

    @staticmethod
    def default_kind():
        return 'business_provider'


class ContractInvoice:
    __name__ = 'contract.invoice'

    commissions = fields.One2Many('contract.invoice.commission',
        'contract_invoice', 'Commissions')


class CommissionInvoice(model.CoopSQL, model.CoopView):
    'Commission Invoice'

    __name__ = 'contract.invoice.commission'

    contract_invoice = fields.Many2One('contract.invoice', 'Contract Invoice',
        required=True, ondelete='CASCADE')
    com_invoice = fields.Many2One('account.invoice', 'Commission Invoice',
        domain=[('type', '=', 'in_invoice')], ondelete='RESTRICT')


class Invoice:
    __name__ = 'account.invoice'

    com_invoices = fields.Function(
        fields.One2Many('account.invoice', None, 'Commission Invoices',
            states={'invisible': Bool(Eval('contract_invoice', False))},
            depends=['contract_invoice']),
        'get_com_invoices')
    contract_invoice = fields.Function(
        fields.Many2One('account.invoice', 'Contract Invoice',
            states={'invisible': ~Eval('contract_invoice')}),
        'get_contract_invoice')

    @classmethod
    def get_contract_invoice(cls, instances, name):
        res = dict((m.id, None) for m in instances)
        cursor = Transaction().cursor

        pool = Pool()
        contract_invoice = pool.get('contract.invoice').__table__()
        contract_commission_invoice = pool.get(
            'contract.invoice.commission').__table__()
        invoice = cls.__table__()

        query_table = invoice.join(contract_commission_invoice,
            condition=(contract_commission_invoice.com_invoice == invoice.id)
            ).join(contract_invoice, condition=(
                    contract_commission_invoice.contract_invoice ==
                    contract_invoice.id))

        cursor.execute(*query_table.select(invoice.id,
                contract_invoice.invoice,
                where=(invoice.id.in_([x.id for x in instances]))))

        for invoice_id, value in cursor.fetchall():
            res[invoice_id] = value
        return res

    @classmethod
    def get_com_invoices(cls, instances, name):
        res = dict((m.id, []) for m in instances)
        cursor = Transaction().cursor

        pool = Pool()
        contract_invoice = pool.get('contract.invoice').__table__()
        contract_commission_invoice = pool.get(
            'contract.invoice.commission').__table__()
        invoice = cls.__table__()

        query_table = invoice.join(contract_invoice,
            condition=(contract_invoice.invoice == invoice.id)
            ).join(contract_commission_invoice, condition=(
                    contract_commission_invoice.contract_invoice ==
                    contract_invoice.id))

        cursor.execute(*query_table.select(invoice.id,
                contract_commission_invoice.com_invoice,
                where=(invoice.id.in_([x.id for x in instances]))))

        for invoice_id, value in cursor.fetchall():
            res[invoice_id].append(value)
        return res


class Premium:
    __name__ = 'contract.premium'

    commissions = fields.One2Many('contract.premium.commission', 'premium',
        'Commissions')

    @classmethod
    def new_line(cls, line, start_date, end_date):
        new_instance = super(Premium, cls).new_line(line, start_date, end_date)
        if not line['commissions']:
            return new_instance
        new_instance.commissions = [{
                'com_option': com_def['option'].com_option.coverage.id,
                'rate': com_def['rate'],
                'party': com_def['option'].com_option.contract.subscriber.id}
            for com_def in line['commissions']]
        return new_instance

    def same_value(self, other):
        result = super(Premium, self).same_value(other)
        if not result:
            return result
        self_dict = dict((x.com_option.id, x.rate) for x in self.commissions)
        other_dict = dict((x.com_option.id, x.rate) for x in other.commissions)
        return self_dict == other_dict


class PremiumCommission(model.CoopSQL, model.CoopView):
    'Premium Commission'

    __name__ = 'contract.premium.commission'

    premium = fields.Many2One('contract.premium', 'Premium',
        ondelete='CASCADE')
    com_option = fields.Many2One('offered.option.description',
        'Commission Coverage', domain=[('kind', '=', 'commission')],
        required=True, ondelete='RESTRICT')
    rate = fields.Numeric('Commission Rate', digits=(7, 6))
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='RESTRICT')

    def get_description(self):
        return '[%s] %s : %.4f %%' % (
            self.com_option.rec_name,
            self.party.name,
            self.rate * 100)

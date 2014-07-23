import datetime
from collections import defaultdict
from decimal import Decimal

from dateutil.rrule import rrule, YEARLY, MONTHLY, DAILY
from dateutil.relativedelta import relativedelta
from sql.aggregate import Max
from sql import Column, Union
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, And, Len, If, Bool
from trytond import backend
from trytond.transaction import Transaction
from trytond.tools import reduce_ids
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.rpc import RPC

from trytond.modules.cog_utils import coop_date, utils, batchs, model, fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractBillingInformation',
    'ContractInvoice',
    'CoveredElement',
    'ContractOption',
    'ExtraPremium',
    'Premium',
    'PremiumTax',
    'InvoiceContract',
    'InvoiceContractStart',
    'DisplayContractPremium',
    'DisplayContractPremiumDisplayer',
    'DisplayContractPremiumDisplayerPremiumLine',
    'CreateInvoiceContractBatch',
    'PostInvoiceContractBatch',
    ]

FREQUENCIES = [
    ('once_per_contract', 'Once Per Contract'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('half_yearly', 'Half-yearly'),
    ('yearly', 'Yearly'),
    ]

PREMIUM_FREQUENCIES = FREQUENCIES + [
    ('yearly_360', 'Yearly (360 days)'),
    ('yearly_365', 'Yearly (365 days)'),
    ('once_per_invoice', 'Once per Invoice'),
    ]


class Contract:
    __name__ = 'contract'
    invoices = fields.One2Many('contract.invoice', 'contract', 'Invoices')
    premiums = fields.One2Many('contract.premium', 'contract', 'Premiums')
    payment_term = fields.Function(fields.Many2One(
        'account.invoice.payment_term', 'Payment Term'),
        'get_billing_information')
    billing_mode = fields.Function(
        fields.Many2One('offered.billing_mode', 'Billing Mode'),
        'get_billing_information')
    billing_information = fields.Function(
        fields.Many2One('contract.billing_information',
            'Current Billing Information'), 'get_billing_information')
    billing_informations = fields.One2Many('contract.billing_information',
        'contract', 'Billing Information', domain=[
            ('billing_mode.products', '=', Eval('product')),
            If(Bool(Eval('subscriber', False)),
                ['OR',
                    ('direct_debit_account.owners', '=', Eval('subscriber')),
                    ('direct_debit_account', '=', None)],
                [('direct_debit_account', '=', None)])],
        depends=['product'])
    last_invoice_start = fields.Function(
        fields.Date('Last Invoice Start Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    last_invoice_end = fields.Function(
        fields.Date('Last Invoice End Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    account_invoices = fields.Many2Many('contract.invoice', 'contract',
        'invoice', 'Invoices', order=[('start', 'ASC')], readonly=True)
    total_invoice_amount = fields.Function(
        fields.Numeric('Total Invoice Amount', digits=(16,
                Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_total_invoice_amount')
    first_year_invoices = fields.Function(
        fields.One2Many('account.invoice', None, 'First Year Invoices'),
        'get_first_year_invoices')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_prices': {},
                })

    @classmethod
    def get_billing_information(cls, contracts, names):
        pool = Pool()
        ContractBillingInformation = pool.get('contract.billing_information')
        return cls.get_revision_value(contracts, names,
            ContractBillingInformation)

    @classmethod
    def get_revision_value(cls, contracts, names, ContractRevision):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Transaction().context.get('contract_revision_date',
            Date.today())
        return ContractRevision.get_values(contracts, names=names, date=date)

    def get_total_invoice_amount(self, name):
        return sum([x.invoice.total_amount
                for x in self.invoices
                if x.invoice.state in ('paid', 'validated', 'posted')])

    @classmethod
    def get_last_invoice(cls, contracts, name):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        cursor = Transaction().cursor
        table = cls.__table__()
        contract_invoice = ContractInvoice.__table__()
        invoice = Invoice.__table__()
        values = dict.fromkeys((c.id for c in contracts))
        column = name[len('last_invoice_'):]
        in_max = cursor.IN_MAX
        for i in range(0, len(contracts), in_max):
            sub_ids = [c.id for c in contracts[i:i + in_max]]
            where_id = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(contract_invoice, 'LEFT',
                    table.id == contract_invoice.contract
                    ).join(invoice, 'LEFT',
                    invoice.id == contract_invoice.invoice
                    ).select(table.id, Max(getattr(contract_invoice, column)),
                    where=where_id & (invoice.state != 'cancel'),
                    group_by=table.id))
            values.update(dict(cursor.fetchall()))
        return values

    @classmethod
    def search_last_invoice(cls, name, domain):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        table = cls.__table__()
        contract_invoice = ContractInvoice.__table__()
        invoice = Invoice.__table__()

        column = name[len('last_invoice_'):]
        _, operator, value = domain
        Operator = fields.SQL_OPERATORS[operator]
        query = table.join(contract_invoice, 'LEFT',
            table.id == contract_invoice.contract
            ).join(invoice, 'LEFT',
                invoice.id == contract_invoice.contract
                ).select(table.id,
                    where=invoice.state != 'cancel',
                    group_by=table.id,
                    having=Operator(Max(getattr(contract_invoice, column)),
                        value))
        return [('id', 'in', query)]

    def _get_invoice_rrule_and_billing_information(self, start):
        billing_informations = iter(self.billing_informations)
        billing_information = billing_informations.next()
        for next_billing_information in billing_informations:
            if next_billing_information.date > start:
                break
            else:
                billing_information = next_billing_information
        else:
            next_billing_information = None
        until = None
        if next_billing_information:
            until = next_billing_information.date
        invoice_rrule = billing_information.billing_mode.get_rrule(start,
            until)
        return (invoice_rrule[0], invoice_rrule[1], billing_information)

    def get_invoice_periods(self, up_to_date):
        if self.last_invoice_end:
            start = self.last_invoice_end + relativedelta(days=+1)
        else:
            start = self.start_date
        if up_to_date and start > up_to_date:
            return []
        periods = []
        while (up_to_date and start < up_to_date) or len(periods) < 1:
            rule, until, billing_information =\
                self._get_invoice_rrule_and_billing_information(start)
            for date in rule:
                if hasattr(date, 'date'):
                    date = date.date()
                if date == start:
                    continue
                end = date + relativedelta(days=-1)
                periods.append((start, min(end, self.end_date or
                            datetime.date.max), billing_information))
                start = date
                if (up_to_date and start >= up_to_date) or not up_to_date:
                    break
            if until and (up_to_date and until < up_to_date):
                if self.end_date and self.end_date < up_to_date:
                    if until > self.end_date:
                        until = self.end_date
                if start != until:
                    end = until + relativedelta(days=-1)
                    periods.append((start, end, billing_information))
                    start = until
        return periods

    @classmethod
    def delete_safe_invoices(cls, contracts, from_date=None, to_date=None):
        # Delete invoices which are either draft or validated (for which no
        # accounting has been done yet)
        # This includes contract_invoices and account_invoices
        pool = Pool()
        cursor = Transaction().cursor
        ContractInvoice = pool.get('contract.invoice')
        AccountInvoice = pool.get('account.invoice')

        contract_invoice = ContractInvoice.__table__()
        account_invoice = AccountInvoice.__table__()

        contract_invoices_to_delete, account_invoices_to_delete = [], []
        in_max = cursor.IN_MAX

        for i in range(0, len(contracts), in_max):
            # Find all account_invoices which are draft
            query_table = contract_invoice.join(account_invoice,
                condition=contract_invoice.contract.in_([
                        x.id for x in contracts[i:i+in_max]])
                & (contract_invoice.invoice == account_invoice.id)
                & (contract_invoice.start >= (from_date or datetime.date.min))
                & (contract_invoice.end <= (to_date or datetime.date.max))
                & account_invoice.state.in_(['draft', 'validated'])
                & (account_invoice.move == None))

            cursor.execute(*query_table.select(contract_invoice.id,
                    account_invoice.id))

            for contract_invoice_id, account_invoice_id in cursor.fetchall():
                contract_invoices_to_delete.append(contract_invoice_id)
                account_invoices_to_delete.append(account_invoice_id)

        for i in range(0, len(contract_invoices_to_delete), in_max):
            if contract_invoices_to_delete:
                cursor.execute(*contract_invoice.delete(
                        where=(account_invoice.id.in_(
                                    contract_invoices_to_delete[i:i + in_max]
                                ))))

        for i in range(0, len(account_invoices_to_delete), in_max):
            if account_invoices_to_delete:
                cursor.execute(*account_invoice.delete(
                        where=(account_invoice.id.in_(
                                    account_invoices_to_delete[i:i + in_max]
                                ))))

    def first_invoice(self):
        # Used to generate the first invoice(s) of the contract. It starts
        # with deleting all existing invoices,  and should not be called if
        # there are paid / posted invoices
        self.delete_safe_invoices([self])
        self.invoice([self], self.start_date)

    @classmethod
    def invoice(cls, contracts, up_to_date):
        'Invoice contracts up to the date'
        periods = defaultdict(list)
        for contract in contracts:
            if contract.status not in ('active', 'quote'):
                continue
            for period in contract.get_invoice_periods(min(up_to_date,
                        contract.end_date or datetime.date.max)):
                periods[period].append(contract)
        return cls.invoice_periods(periods)

    @classmethod
    def invoice_periods(cls, periods):
        'Invoice periods for contracts'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Journal = pool.get('account.journal')
        journals = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None

        invoices = defaultdict(list)
        for period, contracts in periods.iteritems():
            for contract in contracts:
                invoice = contract.get_invoice(*period)
                if not invoice.journal:
                    invoice.journal = journal
                if (not invoice.invoice_address
                        and contract.subscriber.addresses):
                    #TODO : To enhance
                    invoice.invoice_address = contract.subscriber.addresses[0]
                invoice.lines = contract.get_all_invoice_lines(*period[0:2])
                invoices[period].append((contract, invoice))
        new_invoices = Invoice.create([i._save_values
                 for contract_invoices in invoices.itervalues()
                 for c, i in contract_invoices])
        Invoice.update_taxes(new_invoices)
        # Set the new ids
        old_invoices = (i for ci in invoices.itervalues() for c, i in ci)
        for invoice, new_invoice in zip(old_invoices, new_invoices):
            invoice.id = new_invoice.id
        contract_invoices_to_create = []
        for period, contract_invoices in invoices.iteritems():
            start, end, billing_information = period
            for contract, invoice in contract_invoices:
                contract_invoices_to_create.append(ContractInvoice(
                        contract=contract,
                        invoice=invoice,
                        start=start,
                        end=end))
        return ContractInvoice.create([c._save_values
                for c in contract_invoices_to_create])

    def get_invoice(self, start, end, billing_information):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice(
            company=self.company,
            type='out_invoice',
            journal=None,
            party=self.subscriber,
            invoice_address=self.get_contract_address(),
            currency=self.get_currency(),
            account=self.subscriber.account_receivable,
            payment_term=billing_information.payment_term,
            state='validated',
            )

    def get_invoice_line_queries(self, start, end):
        pool = Pool()
        covered_element = pool.get('contract.covered_element').__table__()
        option = pool.get('contract.option').__table__()
        extra_premium = pool.get('contract.option.extra_premium').__table__()

        def table_premium():
            premium = pool.get('contract.premium').__table__()
            date_condition = (
                (Coalesce(premium.start, datetime.date.min) <= end)
                & (Coalesce(premium.end, datetime.date.max) >= start))
            return premium, date_condition

        premium, date_condition = table_premium()
        contract_query = premium.select(premium.id, where=(
                premium.contract == self.id) & date_condition)

        premium, date_condition = table_premium()
        covered_element_query = premium.join(covered_element, condition=(
                covered_element.id == premium.covered_element)
            & (covered_element.contract == self.id)).select(premium.id,
            where=date_condition)

        premium, date_condition = table_premium()
        option_query = premium.join(option, condition=(
                option.id == premium.option)
            & (option.contract == self.id)).select(premium.id,
            where=date_condition)

        premium, date_condition = table_premium()
        option = pool.get('contract.option').__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        covered_option_query = premium.join(option, condition=(
                option.id == premium.option)
            ).join(covered_element, condition=(
                option.covered_element == covered_element.id)
            & (covered_element.contract == self.id)).select(premium.id,
            where=date_condition)

        premium, date_condition = table_premium()
        option = pool.get('contract.option').__table__()
        extra_premium_query = premium.join(extra_premium, condition=(
                extra_premium.id == premium.extra_premium)
            ).join(option, condition=(
                    option.id == extra_premium.option)
            & (option.contract == self.id)).select(premium.id,
            where=date_condition)

        premium, date_condition = table_premium()
        option = pool.get('contract.option').__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        extra_premium = pool.get('contract.option.extra_premium').__table__()
        covered_extra_premium_query = premium.join(extra_premium, condition=(
                extra_premium.id == premium.extra_premium)
            ).join(option, condition=(
                option.id == extra_premium.option)
            ).join(covered_element, condition=(
                option.covered_element == covered_element.id)
            & (covered_element.contract == self.id)).select(premium.id,
            where=date_condition)

        return {
            'contract': contract_query,
            'covered_element': covered_element_query,
            'option': option_query,
            'covered_option': covered_option_query,
            'extra_premium': extra_premium_query,
            'covered_extra_premium': covered_extra_premium_query,
            }

    def get_all_invoice_lines(self, start, end):
        Premium = Pool().get('contract.premium')
        # Returns all contract related invoice lines mathing start / end date
        queries = self.get_invoice_line_queries(start, end)

        cursor = Transaction().cursor
        cursor.execute(*Union(*queries.itervalues()))

        ids = [y for x in cursor.fetchall() for y in x]
        lines = Premium.browse(ids)
        invoice_lines = []
        currency = self.get_currency()
        for line in lines:
            invoice_lines += line.generate_invoice_lines(currency, start, end)
        return invoice_lines

    @classmethod
    @ModelView.button
    def button_calculate_prices(cls, contracts):
        for contract in contracts:
            contract.calculate_prices()

    def before_activate(self, contract_dict=None):
        super(Contract, self).before_activate(contract_dict)
        self.save()
        self.calculate_prices()

    @classmethod
    def calculate_prices(cls, contracts, start=None, end=None):
        final_prices = []
        for contract in contracts:
            prices, errs = contract.calculate_prices_between_dates(start, end)
            if errs:
                return False, errs
            final_prices += prices
        cls.store_prices(prices)
        return True, ()

    def calculate_price_at_date(self, date):
        cur_dict = {
            'date': date,
            'appliable_conditions_date': self.appliable_conditions_date}
        self.init_dict_for_rule_engine(cur_dict)
        prices, errs = self.product.get_result('total_price', cur_dict)
        return (prices, errs)

    def calculate_prices_between_dates(self, start=None, end=None):
        if not start:
            start = self.start_date
        prices = {}
        errs = []
        dates = self.get_dates()
        dates = utils.limit_dates(dates, self.start_date)
        for cur_date in dates:
            price, err = self.calculate_price_at_date(cur_date)
            if price:
                prices[cur_date] = price
            errs += err
            if errs:
                return {}, errs
        return prices, errs

    @classmethod
    def store_price(cls, price, start_date, end_date):
        Premium = Pool().get('contract.premium')
        new_premium = Premium.new_line(price, start_date, end_date)
        return [new_premium] if new_premium else []

    @classmethod
    def store_prices(cls, prices):
        if not prices:
            return
        pool = Pool()
        Premium = pool.get('contract.premium')
        dates = list(prices.iterkeys())
        dates.sort()
        to_save = []
        parents_to_update = {}
        for date, price_list in prices.iteritems():
            date_pos = dates.index(date)
            if date_pos < len(dates) - 1:
                end_date = dates[date_pos + 1] + datetime.timedelta(days=-1)
            else:
                end_date = None
            for price in price_list:
                prices = cls.store_price(price, start_date=date,
                    end_date=end_date)
                to_save += prices
        for premium in to_save:
            if premium.parent in parents_to_update:
                parents_to_update[premium.parent]['save'].append(premium)
            else:
                parents_to_update[premium.parent] = {
                    'save': [premium],
                    'delete': [],
                    'keep': [],
                    'write': [],
                    }
        for elem in parents_to_update.iterkeys():
            existing = [x for x in getattr(elem, 'premiums', []) if x.id > 0]
            for premium in existing:
                if premium.start >= dates[0]:
                    parents_to_update[elem]['delete'].append(premium)
                elif datetime.date.min or elem.start < dates[0] <= (
                        elem.end or datetime.date.max):
                    elem.end = coop_date.add_day(dates[0], -1)
                    parents_to_update[elem]['write'].append(premium)
                else:
                    parents_to_update[elem]['keep'].append(premium)
            Premium.remove_duplicates(elem, parents_to_update[elem])

        for elem in parents_to_update.iterkeys():
            if not elem._values:
                continue
            elem.save()

    def get_premium_list(self):
        result = list(self.premiums)
        for option in self.options:
            result.extend(option.get_premium_list())
        for covered_element in self.covered_elements:
            result.extend(covered_element.get_premium_list())
        return result

    def init_from_product(self, product, start_date=None, end_date=None):
        pool = Pool()
        res, errs = super(Contract, self).init_from_product(product,
            start_date, end_date)
        BillingInformation = pool.get('contract.billing_information')
        if not product.billing_modes:
            return res, errs
        default_billing_mode = product.billing_modes[0]
        if default_billing_mode.direct_debit:
            days = default_billing_mode.get_allowed_direct_debit_days()
            direct_debit_day = days[0][0]
        else:
            direct_debit_day = 0
        self.billing_informations = [BillingInformation(start=self.start_date,
            billing_mode=default_billing_mode,
            payment_term=default_billing_mode.allowed_payment_terms[0],
            direct_debit_day=direct_debit_day)]
        return res, errs

    def get_first_year_invoices(self, name):
        AccountInvoice = Pool().get('account.invoice')
        to_date = coop_date.add_duration(self.start_date, 'year')
        return [x.id for x in AccountInvoice.search([
                    ('contract', '=', self.id),
                    ('start', '<', to_date),
                    ])]


class ContractBillingInformation(model._RevisionMixin, model.CoopSQL,
        model.CoopView):
    'Contract Billing Information'
    __name__ = 'contract.billing_information'

    _parent_name = 'contract'
    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE')
    billing_mode = fields.Many2One('offered.billing_mode', 'Billing Mode',
        required=True, ondelete='CASCADE')
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', ondelete='CASCADE', states={
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active')),
            'invisible': Len(Eval('possible_payment_terms', [])) < 2},
        domain=[('id', 'in', Eval('possible_payment_terms'))],
        depends=['possible_payment_terms'])
    direct_debit = fields.Function(
        fields.Boolean('Direct Debit Payment'), 'on_change_with_direct_debit')
    direct_debit_day_selector = fields.Function(
        fields.Selection('get_allowed_direct_debit_days',
            'Direct Debit Day', states={
                'invisible': ~Eval('direct_debit', False),
                'required': And(Eval('direct_debit', False),
                    (Eval('_parent_contract', {}).get('status', '') ==
                        'active'))},
            sort=False, depends=['direct_debit']),
            'get_direct_debit_day_selector', 'set_direct_debit_day_selector')
    direct_debit_day = fields.Integer('Direct Debit Day')
    direct_debit_account = fields.Many2One('bank.account',
        'Direct Debit Account',
        states={'invisible': ~Eval('direct_debit'),
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active'))},
        depends=['direct_debit'])
    possible_payment_terms = fields.Function(fields.One2Many(
            'account.invoice.payment_term', None, 'Possible Payment Term'),
            'on_change_with_possible_payment_terms')

    @classmethod
    def __setup__(cls):
        super(ContractBillingInformation, cls).__setup__()
        cls.__rpc__.update({
                'get_allowed_direct_debit_days': RPC(instantiate=0)
                })

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        if (not TableHandler.table_exist(cursor,
                'contract_billing_information') and TableHandler.table_exist(
                    cursor, 'contract_invoice_frequency')):
            migrate = True

        super(ContractBillingInformation, cls).__register__(module_name)

        # Migration from 1.1: Billing change
        if migrate:
            cursor.execute('insert into '
                '"contract_billing_information" '
                '(id, create_uid, create_date, write_uid, write_date,'
                'billing_mode, contract, date, direct_debit_day, '
                'direct_debit_account) '
                'select f.id, f.create_uid, f.create_date, f.write_uid, '
                'f.write_date, f.value, f.contract, f.date, '
                'cast(c.direct_debit_day as integer), '
                'c.direct_debit_account from '
                'contract_invoice_frequency as f, '
                'contract as c where f.contract = c.id')

    @staticmethod
    def revision_columns():
        return ['billing_mode', 'payment_term', 'direct_debit_day',
            'direct_debit_account']

    @classmethod
    def get_reverse_field_name(cls):
        return 'billing_information'

    @fields.depends('billing_mode')
    def get_allowed_direct_debit_days(self):
        if not self.billing_mode:
            return [('', '')]
        return self.billing_mode.get_allowed_direct_debit_days()

    def get_direct_debit_day_selector(self, name):
        if not self.direct_debit:
            return ''
        return str(self.direct_debit_day)

    @classmethod
    def set_direct_debit_day_selector(cls, ids, name, value):
        if not value:
            return
        cls.write(ids, {'direct_debit_day': int(value)})

    @fields.depends('billing_mode')
    def on_change_with_direct_debit(self, name=None):
        if self.billing_mode:
            return self.billing_mode.direct_debit

    @fields.depends('billing_mode')
    def on_change_with_possible_payment_terms(self, name=None):
        if not self.billing_mode:
            return []
        return [x.id for x in self.billing_mode.allowed_payment_terms]

    @fields.depends('billing_mode')
    def on_change_with_payment_term(self, name=None):
        if self.billing_mode:
            return self.billing_mode.allowed_payment_terms[0].id

    @fields.depends('direct_debit_day_selector')
    def on_change_direct_debit_day_selector(self):
        if not self.direct_debit_day_selector:
            return {'direct_debit_day': None}
        return {'direct_debit_day': int(self.direct_debit_day_selector)}


class ContractInvoice(ModelSQL, ModelView):
    'Contract Invoice'
    __name__ = 'contract.invoice'
    contract = fields.Many2One('contract', 'Contract', required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', required=True,
        ondelete='CASCADE')
    invoice_state = fields.Function(
        fields.Char('Invoice State'),
        'get_invoice_state', searcher='search_invoice_state')
    start = fields.Date('Start Date', required=True)
    end = fields.Date('End Date', required=True)

    @classmethod
    def __setup__(cls):
        super(ContractInvoice, cls).__setup__()
        cls._order.insert(0, ('start', 'DESC'))
        cls._buttons.update({
                'reinvoice': {
                    'invisible': Eval('invoice_state') == 'cancel',
                    },
                'cancel': {
                    'invisible': Eval('invoice_state') == 'cancel',
                    },
                })

    def get_invoice_state(self, name):
        return self.invoice.state

    @classmethod
    def search_invoice_state(cls, name, domain):
        return [('invoice.state',) + tuple(domain[1:])]

    @classmethod
    def validate(cls, contract_invoices):
        super(ContractInvoice, cls).validate(contract_invoices)
        for contract_invoice in contract_invoices:
            contract_invoice.check_dates()

    def check_dates(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        cursor = Transaction().cursor
        table = self.__table__()
        invoice = Invoice.__table__()
        cursor.execute(*table.join(invoice,
                condition=table.invoice == invoice.id
                ).select(table.id,
                where=(((table.start <= self.start)
                        & (table.end >= self.start))
                    | ((table.start <= self.end)
                        & (table.end >= self.end))
                    | ((table.start >= self.start)
                        & (table.end <= self.end)))
                    & (table.contract == self.id)
                    & (invoice.state != 'cancel')))

    @classmethod
    @ModelView.button
    def reinvoice(cls, contract_invoices):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Contract = pool.get('contract')
        invoices = []
        for contract_invoice in contract_invoices:
            assert contract_invoice.invoice_state != 'cancel'
            invoices.append(contract_invoice.invoice)
        Invoice.cancel(invoices)
        periods = defaultdict(list)
        for contract_invoice in contract_invoices:
            period = contract_invoice.start, contract_invoice.end
            periods[period].append(contract_invoice.contract)
        Contract.invoice_periods(periods)

    @classmethod
    @ModelView.button
    def cancel(cls, contract_invoices):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        Invoice = pool.get('account.invoice')

        invoices = [c.invoice for c in contract_invoices]
        reconciliations = []
        for invoice in invoices:
            if invoice.move:
                for line in invoice.move.lines:
                    if line.reconciliation:
                        reconciliations.append(line.reconciliation)
        if reconciliations:
            Reconciliation.delete(reconciliations)
        Invoice.cancel(invoices)

    @classmethod
    def delete(cls, contract_invoices):
        invoices_to_cancel, invoices_to_delete = [], []
        for invoice in contract_invoices:
            if invoice.invoice_state in ('posted', 'paid'):
                invoices_to_cancel.append(invoice)
            elif invoice.invoice_state in ('validated', 'draft'):
                invoices_to_delete.append(invoice)
        if invoices_to_cancel:
            cls.cancel(invoices_to_cancel)
        if invoices_to_delete:
            super(ContractInvoice, cls).delete(invoices_to_delete)


class CoveredElement:
    __name__ = 'contract.covered_element'

    premiums = fields.One2Many('contract.premium', 'covered_element',
        'Premiums')

    def get_premium_list(self):
        result = list(self.premiums)
        for option in self.options:
            result.extend(option.get_premium_list())
        return result


class ContractOption:
    __name__ = 'contract.option'

    premiums = fields.One2Many('contract.premium', 'option', 'Premiums')

    def get_premium_list(self):
        result = list(self.premiums)
        for extra_premium in self.extra_premiums:
            result.extend(extra_premium.get_premium_list())
        return result


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    premiums = fields.One2Many('contract.premium', 'extra_premium',
        'Premiums')

    def get_premium_list(self):
        return list(self.premiums)


class Premium(ModelSQL, ModelView):
    'Premium'
    __name__ = 'contract.premium'
    contract = fields.Many2One('contract', 'Contract', select=True,
        ondelete='CASCADE')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', select=True, ondelete='CASCADE')
    option = fields.Many2One('contract.option', 'Option', select=True,
        ondelete='CASCADE')
    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium', select=True, ondelete='CASCADE')
    rated_entity = fields.Reference('Rated Entity', 'get_rated_entities',
        required=True)
    start = fields.Date('Start')
    end = fields.Date('End')
    amount = fields.Numeric('Amount', required=True)
    frequency = fields.Selection(PREMIUM_FREQUENCIES, 'Frequency', sort=False)
    taxes = fields.Many2Many('contract.premium-account.tax',
        'premium', 'tax', 'Taxes',
        domain=[
            ('parent', '=', None),
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both']),
                ],
            ])
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ('kind', '=', 'revenue'),
            ])
    invoice_lines = fields.One2Many('account.invoice.line', 'origin',
        'Invoice Lines', readonly=True)
    main_contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_main_contract')
    parent = fields.Function(
        fields.Reference('Parent', 'get_parent_models'),
        'get_parent')

    @classmethod
    def __setup__(cls):
        super(Premium, cls).__setup__()
        cls._order = [('rated_entity', 'ASC'), ('start', 'ASC')]

    @classmethod
    def _get_rated_entities(cls):
        'Return list of Model names for origin Reference'
        return [
            'offered.product',
            'offered.option.description',
            'account.fee.description',
            ]

    @classmethod
    def get_rated_entities(cls):
        Model = Pool().get('ir.model')
        models = cls._get_rated_entities()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod
    def get_possible_parent_field(cls):
        return set(['contract', 'covered_element', 'option', 'extra_premium'])

    @classmethod
    def get_parent_models(cls):
        result = []
        for field_name in cls.get_possible_parent_field():
            field = cls._fields[field_name]
            result.append((field.model_name, field.string))
        return result

    @classmethod
    def get_parent(cls, premiums, name):
        cursor = Transaction().cursor
        premium_table = cls.__table__()
        models, columns = [], []
        for field_name in cls.get_possible_parent_field():
            field = cls._fields[field_name]
            models.append(field.model_name)
            columns.append(Column(premium_table, field_name))

        cursor.execute(*premium_table.select(premium_table.id, *columns,
                where=premium_table.id.in_([x.id for x in premiums])))

        result = {}
        for elem in cursor.fetchall():
            for model_name, value in zip(models, elem[1:]):
                if value:
                    result[elem[0]] = '%s,%i' % (model_name, value)
                    break
        return result

    def get_main_contract(self, name=None):
        if self.contract:
            return self.contract.id
        if self.covered_element:
            return self.covered_element.main_contract.id
        if self.option:
            return self.option.parent_contract.id
        if self.extra_premium:
            return self.extra_premium.option.parent_contract.id

    def get_description(self):
        return '%s - %s' % (self.parent.rec_name,
            self.rated_entity.rec_name)

    def _get_rrule(self, start):
        if self.frequency in ('monthly', 'quarterly', 'half_yearly'):
            freq = MONTHLY
            interval = {
                'monthly': 1,
                'quarterly': 3,
                'half_yearly': 6,
                }.get(self.frequency)
        elif self.frequency == 'yearly':
            freq = YEARLY
            interval = 1
        elif self.frequency == 'yearly_360':
            freq = DAILY
            interval = 360
        elif self.frequency == 'yearly_365':
            freq = DAILY
            interval = 365
        elif self.frequency in ('once_per_contract'):
            return rrule(MONTHLY, dtstart=self.start, count=2)
        else:
            return
        return rrule(freq, interval=interval, dtstart=start)

    def get_amount(self, start, end):
        if self.frequency in ('once_per_invoice'):
            return self.amount
        rrule = self._get_rrule(start)
        start = datetime.datetime.combine(start, datetime.time())
        end = datetime.datetime.combine(end, datetime.time())
        occurences = rrule.between(start, end + datetime.timedelta(2))
        amount = len(occurences) * self.amount
        try:
            last_date = occurences[-1]
        except IndexError:
            last_date = start
        next_date = rrule.after(last_date)
        if self.frequency in ('once_per_contract'):
            if (last_date <= datetime.datetime.combine(self.start,
                    datetime.time()) <= next_date):
                return self.amount
            elif (start <= datetime.datetime.combine(self.start,
                    datetime.time())):
                return self.amount
            else:
                return 0
        if next_date and (next_date - end).days > 1:
            if (end - last_date).days != 0:
                ratio = (((end - last_date).days + 1.)
                    / ((next_date - last_date).days))
                amount += self.amount * Decimal(ratio)
        return amount

    def generate_invoice_lines(self, currency, start, end):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        start = (start if start > (self.start or datetime.date.min)
            else self.start)
        end = end if end < (self.end or datetime.date.max) else self.end
        amount = self.get_amount(start, end)
        if not amount:
            return []
        return [InvoiceLine(
                type='line',
                description=self.get_description(),
                origin=self,
                quantity=1,
                unit=None,
                unit_price=currency.round(amount),
                taxes=self.taxes,
                invoice_type='out_invoice',
                account=self.account,
                coverage_start=start,
                coverage_end=end,
                )]

    def set_parent_from_line(self, line):
        for elem in self.get_possible_parent_field():
            field = self._fields[elem]
            if field.model_name == line['target'].__name__:
                setattr(self, elem, line['target'])
                self.parent = line['target']
                break

    def calculate_rated_entity(self):
        # TODO : use the line rated_entity once it is implemented
        if self.parent.__name__ == 'contract':
            rated_entity = self.parent.product
        elif self.parent.__name__ == 'contract.option':
            rated_entity = self.parent.coverage
        elif self.parent.__name__ == 'contract.covered_element':
            rated_entity = self.parent.contract
        elif self.parent.__name__ == 'extra_premium':
            rated_entity = self.parent.option
        else:
            rated_entity = None
        return rated_entity

    @classmethod
    def new_line(cls, line, start_date, end_date):
        if 'target' not in line:
            return None
        new_instance = cls()
        new_instance.set_parent_from_line(line)
        if not new_instance.parent:
            # TODO : Should raise an error
            return None
        new_instance.rated_entity = line['rated_entity']
        # TODO : use the line account once it is implemented
        new_instance.account = new_instance.rated_entity.account_for_billing
        new_instance.start = start_date
        if getattr(new_instance.parent, 'end_date', None) and (not end_date
                or new_instance.parent.end_date < end_date):
            new_instance.end = new_instance.parent.end_date
        else:
            new_instance.end = end_date
        new_instance.amount = line['amount']
        new_instance.taxes = line.get('taxes', [])
        new_instance.frequency = line['frequency']
        return new_instance

    @classmethod
    def remove_duplicates(cls, parent, actions):
        new_list = []
        for act_name in ['keep', 'write', 'save']:
            new_list += [(act_name, elem) for elem in actions[act_name]]

        def sort_key(action):
            _, premium = action
            return tuple((getattr(premium, fname) for fname, _ in cls._order))

        new_list.sort(key=sort_key)
        final_list = []
        prev_action, prev_premium = None, None
        for elem in new_list:
            action, premium = elem
            if not prev_action:
                prev_action, prev_premium = action, premium
            elif prev_premium.same_value(premium):
                prev_premium.end = premium.end
            else:
                final_list.append(prev_premium)
                prev_action, prev_premium = action, premium

        # Do not forget the final element :)
        final_list.append(prev_premium)
        setattr(parent, 'premiums', final_list)

    def same_value(self, other):
        ident_fields = ('parent', 'amount', 'frequency', 'rated_entity',
            'account')
        for elem in ident_fields:
            if getattr(self, elem) != getattr(other, elem):
                return False
        if set(self.taxes) != set(other.taxes):
            return False
        return True

    def get_rec_name(self, name):
        return '(%s - %s) %s' % (self.start, self.end or '', self.amount)


class PremiumTax(ModelSQL):
    'Premium - Tax'
    __name__ = 'contract.premium-account.tax'
    premium = fields.Many2One('contract.premium', 'Premium',
        ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
        required=True)


class InvoiceContractStart(ModelView):
    'Invoice Contract'
    __name__ = 'contract.invoice.start'
    up_to_date = fields.Date('Up To Date', required=True)


class InvoiceContract(Wizard):
    'Invoice Contract'
    __name__ = 'contract.invoice'
    start = StateView('contract.invoice.start',
        'contract_insurance_invoice.invoice_start_view_form', [
            Button('Cancel', 'end', icon='tryton-cancel'),
            Button('Ok', 'invoice', icon='tryton-ok', default=True),
            ])
    invoice = StateTransition()

    def transition_invoice(self):
        pool = Pool()
        Contract = pool.get('contract')
        contracts = Contract.browse(Transaction().context['active_ids'])
        Contract.invoice(contracts, self.start.up_to_date)
        return 'end'


class DisplayContractPremium(Wizard):
    'Display Contrat Premium'

    __name__ = 'contract.premium.display'

    start_state = 'display'
    display = StateView('contract.premium.display.premiums',
        'contract_insurance_invoice.display_premiums_view_form', [
            Button('Calculate Prices', 'calculate_prices', 'tryton-refresh'),
            Button('Exit', 'end', 'tryton-cancel', default=True)])
    calculate_prices = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DisplayContractPremium, cls).__setup__()
        cls._error_messages.update({
                'no_contract_found': 'No contract found in context',
                })

    @classmethod
    def get_children_fields(cls):
        return {
            'contract': ['options', 'covered_elements'],
            'contract.covered_element': ['options'],
            'contract.option': ['extra_premiums'],
            }

    @classmethod
    def new_line(cls, line=None):
        return {
            'name': '%s - %s' % (line.start, line.end or '') if line else '',
            'premium': line.id if line else None,
            'premiums': [line.id] if line else [],
            'amount': line.amount if line else 0,
            'childs': [],
            }

    def add_lines(self, source, parent):
        for field_name in self.get_children_fields().get(source.__name__, ()):
            values = getattr(source, field_name, None)
            if not values:
                continue
            for elem in values:
                base_line = self.new_line()
                base_line['name'] = elem.rec_name
                self.add_lines(elem, base_line)
                parent['childs'].append(base_line)
                parent['amount'] += base_line['amount']
        if source.premiums:
            premium_root = self.new_line()
            premium_root['name'] = 'Premium'
            for elem in source.premiums:
                premium_line = self.new_line(line=elem)
                if elem.start <= utils.today() <= (
                        elem.end or datetime.date.max):
                    premium_root['amount'] += elem.amount
                premium_root['childs'].append(premium_line)
            parent['childs'].append(premium_root)
            parent['amount'] += premium_root['amount']
        return parent

    def default_display(self, name):
        try:
            contracts = Pool().get('contract').browse(
                Transaction().context.get('active_ids'))
        except:
            self.raise_user_error('no_contract_found')
        lines = []
        for contract in contracts:
            contract_line = self.new_line()
            contract_line['name'] = contract.rec_name
            self.add_lines(contract, contract_line)
            lines.append(contract_line)
        return {'premiums': lines}

    def transition_calculate_prices(self):
        Contract = Pool().get('contract')
        Contract.button_calculate_prices(Contract.browse(
                Transaction().context.get('active_ids', [])))
        return 'display'


class DisplayContractPremiumDisplayer(model.CoopView):
    'Display Contract Premium Displayer'

    __name__ = 'contract.premium.display.premiums'

    premiums = fields.One2Many('contract.premium.display.premiums.line',
        None, 'Premiums', readonly=True)


class DisplayContractPremiumDisplayerPremiumLine(model.CoopView):
    'Display Contract Premium Displayer Prmeium Line'

    __name__ = 'contract.premium.display.premiums.line'

    amount = fields.Numeric('Amount Today')
    childs = fields.One2Many('contract.premium.display.premiums.line', None,
        'Childs')
    premiums = fields.One2Many('contract.premium', None, 'Premium')
    premium = fields.Many2One('contract.premium', 'Premium')
    name = fields.Char('Name')


class CreateInvoiceContractBatch(batchs.BatchRoot):
    'Contract Invoice Creation Batch'

    __name__ = 'contract.invoice.create'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def get_batch_name(cls):
        return 'Contract invoice creation'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 4

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().cursor
        pool = Pool()

        contract = pool.get('contract').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        query_table = contract.join(contract_invoice, 'LEFT', condition=(
                contract.id == contract_invoice.contract))

        cursor.execute(*query_table.select(contract.id, group_by=contract.id,
                where=(contract.status == 'active'),
                having=(
                    (Max(contract_invoice.end) < treatment_date)
                    | (Max(contract_invoice.end) == None))))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, logger, treatment_date):
        Pool().get('contract').invoice(objects, treatment_date)


class PostInvoiceContractBatch(batchs.BatchRoot):
    'Post Contract Invoice Batch'

    __name__ = 'contract.invoice.post'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def get_batch_name(cls):
        return 'Contract invoice posting'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 4

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().cursor
        pool = Pool()

        account_invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        query_table = contract_invoice.join(account_invoice, 'LEFT',
            condition=(account_invoice.id == contract_invoice.invoice))

        cursor.execute(*query_table.select(account_invoice.id,
                where=((contract_invoice.start <= treatment_date)
                    & (account_invoice.state == 'validated'))))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, logger, treatment_date):
        Pool().get('account.invoice').post(objects)

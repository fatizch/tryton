import datetime
from decimal import Decimal
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from sql import Literal
from sql.aggregate import Sum, Max
from sql.conditionals import Case, Coalesce
from sql.functions import Round

from trytond import backend
from trytond.wizard import Wizard, StateView, Button
from trytond.pool import PoolMeta, Pool
from trytond.tools import grouped_slice, reduce_ids
from trytond.pyson import Eval, And, Or
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, utils


__metaclass__ = PoolMeta
__all__ = [
    'LoanShare',
    'ExtraPremium',
    'Premium',
    'PremiumAmount',
    'PremiumAmountPerPeriod',
    'Contract',
    'Loan',
    'AveragePremiumRateLoanDisplayer',
    'DisplayLoanAveragePremiumValues',
    'DisplayLoanAveragePremium',
    ]


class LoanShare:
    __name__ = 'loan.share'

    average_premium_rate = fields.Function(
        fields.Numeric('Average Premium Rate', digits=(6, 4)),
        'get_average_premium_rate')
    base_premium_amount = fields.Function(
        fields.Numeric('Base Premium Amount', digits=(16, 2)),
        'get_average_premium_rate')

    @classmethod
    def get_average_premium_rate(cls, shares, names):
        field_values = {'average_premium_rate': {}, 'base_premium_amount': {}}
        for share in shares:
            contract = share.option.covered_element.contract
            rule = contract.product.average_loan_premium_rule
            vals = rule.calculate_average_premium_for_option(contract, share)
            field_values['base_premium_amount'][share.id] = vals[0] or 0
            field_values['average_premium_rate'][share.id] = vals[1] or 0
        return field_values


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls.flat_amount_frequency.states['invisible'] = And(
            cls.flat_amount_frequency.states['invisible'],
            Eval('calculation_kind', '') != 'capital_per_mil')
        cls.flat_amount_frequency.states['required'] = Or(
            cls.flat_amount_frequency.states['required'],
            Eval('calculation_kind', '') == 'capital_per_mil')


class Premium:
    __name__ = 'contract.premium'

    loan = fields.Many2One('loan', 'Loan', select=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Premium, cls).__setup__()
        # Make sure premiums are properly ordered per loan
        cls._order.insert(0, ('loan', 'ASC'))

    def duplicate_sort_key(self):
        key = super(Premium, self).duplicate_sort_key()
        return tuple([self.loan.id if self.loan else None] + list(key))

    def same_value(self, other):
        return super(Premium, self).same_value(other) and (
            self.loan == other.loan)

    @classmethod
    def new_line(cls, line, start_date, end_date):
        if isinstance(line.rated_instance, Pool().get('loan.share')):
            line.rated_instance = line.rated_instance.option
        result = super(Premium, cls).new_line(line, start_date, end_date)
        result.loan = line.loan
        return result

    def _get_key(self, no_date=False):
        key = super(Premium, self)._get_key(no_date=no_date)
        return (self.loan,) + key


class Contract:
    __name__ = 'contract'

    premium_amounts = fields.One2Many('contract.premium.amount', 'contract',
        'Premium Amounts', readonly=True, delete_missing=True)
    premium_amounts_per_period = fields.One2Many(
        'contract.premium.amount.per_period', 'contract',
        'Premium amounts per period', readonly=True)
    total_premium_amount = fields.Function(
        fields.Numeric('Total Premium Amount',
            digits=(16, Eval('currency_digits', 2)),
            states={'invisible': ~Eval('is_loan')},
            depends=['currency_digits', 'is_loan']),
        'get_total_premium_amount')
    last_generated_premium_end = fields.Function(
        fields.Date('Last Generated Premium End Date'),
        'get_last_generated')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
                'no_premium_found': 'No premium found for this contract !',
                })

    @classmethod
    def _export_skips(cls):
        return super(Contract, cls)._export_skips() | {
            'premium_amounts_per_period'}

    @classmethod
    def functional_skips_for_duplicate(cls):
        return super(Contract, cls).functional_skips_for_duplicate() | {
            'premium_amounts'}

    @classmethod
    def ws_subscribe_contracts(cls, contract_dict):
        with Transaction().set_context(_force_calculate_prices=True):
            return super(Contract, cls).ws_subscribe_contracts(contract_dict)

    @classmethod
    def _ws_extract_rating_message(cls, contracts):
        message = super(Contract, cls)._ws_extract_rating_message(contracts)
        PremiumPerPeriod = Pool().get('contract.premium.amount.per_period')
        for contract in contracts:
            if contract.is_loan:
                message[contract.quote_number] = [
                    PremiumPerPeriod.export_json(x)
                    for x in contract.premium_amounts_per_period]
        return message

    @classmethod
    def reactivate(cls, contracts):
        with Transaction().set_context(_force_calculate_prices=True):
            super(Contract, cls).reactivate(contracts)

    @classmethod
    def get_total_premium_amount(cls, contracts, name):
        cursor = Transaction().cursor
        pool = Pool()
        values = {x.id: Decimal(0) for x in contracts}

        PremiumAggregate = pool.get('contract.premium.amount.per_period')
        premium_aggregate = PremiumAggregate.__table__()
        contract = cls.__table__()

        for contract_slice in grouped_slice(contracts):
            cursor.execute(*contract.join(premium_aggregate, condition=(
                        premium_aggregate.contract == contract.id)
                    ).select(contract.id, Sum(premium_aggregate.total),
                    where=contract.id.in_([x.id for x in contract_slice]),
                    group_by=contract.id))
            values.update(dict(cursor.fetchall()))
        for contract in contracts:
            values[contract.id] = contract.currency.round(values[contract.id])
        return values

    @classmethod
    def get_last_generated(cls, contracts, name):
        pool = Pool()
        PremiumAmount = pool.get('contract.premium.amount')
        cursor = Transaction().cursor
        table = cls.__table__()
        premium_amount = PremiumAmount.__table__()
        values = dict.fromkeys((c.id for c in contracts))
        in_max = cursor.IN_MAX
        for i in range(0, len(contracts), in_max):
            sub_ids = [c.id for c in contracts[i:i + in_max]]
            where_id = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(premium_amount, 'LEFT',
                    table.id == premium_amount.contract
                    ).select(table.id, Max(premium_amount.period_end),
                    where=where_id,
                    group_by=table.id))
            values.update(dict(cursor.fetchall()))
        return values

    @classmethod
    def delete_prices(cls, contracts, limit):
        super(Contract, cls).delete_prices(contracts, limit)
        loan_contracts = [x for x in contracts if x.is_loan]
        if not loan_contracts:
            return
        PremiumAmount = Pool().get('contract.premium.amount')
        premiums_to_delete = []
        for sub_contracts in grouped_slice(loan_contracts):
            premiums_to_delete.extend(PremiumAmount.search([
                        ('contract', 'in', sub_contracts),
                        ['OR',
                            ('end', '>=', limit or datetime.date.max),
                            ('contract.status', '=', 'void')]]))
        PremiumAmount.delete(premiums_to_delete)

    @classmethod
    def calculate_prices(cls, contracts, start=None, end=None):
        result = super(Contract, cls).calculate_prices(contracts, start, end)
        loan_contracts = [x for x in contracts if x.is_loan]
        if not loan_contracts:
            return result
        cls.generate_premium_amount(loan_contracts)
        return result

    @property
    def _premium_aggregates_cache(self):
        if hasattr(self, '__premium_cache'):
            return self.__premium_cache
        self.__premium_cache = {}
        return self.__premium_cache

    def _clear_premium_aggregates_cache(self):
        self.__premium_cache = {}

    def calculate_premium_aggregates(self, start=None, end=None):
        cached_values = self._premium_aggregates_cache.get(
            (self.id, start, end), None)
        if cached_values:
            return cached_values
        cursor = Transaction().cursor
        pool = Pool()
        Premium = pool.get('contract.premium')
        PremiumAmount = pool.get('contract.premium.amount')
        premium_amount = PremiumAmount.__table__()

        date_clause = ((premium_amount.end >= (start or datetime.date.min))
            & (premium_amount.start <= (end or datetime.date.max)))
        cursor.execute(*premium_amount.select(
                Coalesce(premium_amount.amount, Literal(0)) + Coalesce(
                    premium_amount.tax_amount, Literal(0)),
                premium_amount.premium,
                where=date_clause & (premium_amount.contract == self.id)))

        per_contract_entity = defaultdict(
            lambda: defaultdict(lambda: Decimal(0)))
        per_offered_entity = defaultdict(
            lambda: defaultdict(lambda: Decimal(0)))

        # Unzip first to browse all premiums at once
        query_result = cursor.fetchall()
        if not query_result:
            self.raise_user_error('no_premium_found')
        amounts, premiums = zip(*query_result)
        premiums = Premium.browse(premiums)
        for amount, premium in zip(amounts, premiums):
            per_contract_entity[(premium.parent.__name__, premium.parent.id)][
                premium.loan.id if premium.loan else None] += amount
            per_offered_entity[(premium.rated_entity.__name__,
                    premium.rated_entity.id)][
                        premium.loan.id if premium.loan else None] += amount

        self._premium_aggregates_cache[(self.id, start, end)] = (
            per_contract_entity, per_offered_entity)
        return per_contract_entity, per_offered_entity

    def extract_premium(self, kind, start=None, end=None, value=None,
            model_name='', loan=None):
        # Returns a function that can be used to browse the queries results
        # and aggregating them. It is possible to aggregate per model_name,
        # per a specific parent (eg. per covered_element), or per offered
        # entity (eg. offered coverage)
        assert kind in ('offered', 'contract')
        per_contract_entity, per_offered_entity = \
            self.calculate_premium_aggregates(start, end)
        values = {}
        if kind == 'offered':
            values = per_offered_entity
        elif kind == 'contract':
            values = per_contract_entity
        if value:
            good_dict = values[(value.__name__, value.id)]
            if loan:
                return good_dict[loan.id]
            return sum(good_dict.values())
        if model_name:
            result = sum([self.extract_premium(kind, start, end, values=k,
                        loan=loan)
                    for k, v in values.iteritems()
                    if k[0] == model_name])
            return result
        return values

    def get_invoice_lines(self, start, end):
        pool = Pool()
        Amount = pool.get('contract.premium.amount')
        InvoiceLine = pool.get('account.invoice.line')
        InvoiceLineDetail = pool.get('account.invoice.line.detail')
        if not self.is_loan:
            return super(Contract, self).get_invoice_lines(start, end)
        lines = []
        amounts = Amount.search([
                ('period_start', '=', start),
                ('period_end', '=', end),
                ('contract', '=', self.id),
                ])
        for amount in amounts:
            line = InvoiceLine(
                type='line',
                description=amount.premium.get_description(),
                origin=self,
                quantity=1,
                unit=None,
                unit_price=amount.amount,
                taxes=amount.premium.taxes,
                invoice_type='out_invoice',
                account=amount.premium.account,
                coverage_start=amount.start,
                coverage_end=amount.end,
                details=[InvoiceLineDetail.new_detail_from_premium(
                        amount.premium)],
                )
            lines.append(line)
        self.finalize_invoices_lines(lines)
        return lines

    @classmethod
    def generate_premium_amount(cls, contracts):
        'Generate premium amount up to the contract end_date'
        pool = Pool()
        Amount = pool.get('contract.premium.amount')
        Tax = pool.get('account.tax')
        config = pool.get('account.configuration')(1)
        amounts = []
        for contract in contracts:
            if not contract.is_loan:
                continue
            contract._clear_premium_aggregates_cache()
            if contract.status == 'void':
                continue
            assert contract.end_date
            generation_start = contract.start_date
            if contract.last_generated_premium_end:
                generation_start = contract.last_generated_premium_end + \
                    relativedelta(days=+1)
            for period in contract.get_invoice_periods(contract.end_date,
                    generation_start):
                period = period[:2]  # XXX there is billing information
                invoice_lines = contract.compute_invoice_lines(*period)
                for invoice_line in invoice_lines:
                    taxes = Tax.compute(invoice_line.taxes,
                        invoice_line.unit_price, invoice_line.quantity,
                        date=period[0])
                    if config.tax_rounding == 'line':
                        tax_amount = sum(contract.currency.round(t['amount'])
                            for t in taxes)
                    else:
                        tax_amount = sum(t['amount'] for t in taxes)
                    amount = Amount(
                        premium=invoice_line.details[0].premium,
                        period_start=period[0],
                        period_end=period[1],
                        start=invoice_line.coverage_start,
                        end=invoice_line.coverage_end,
                        amount=invoice_line.unit_price,
                        tax_amount=tax_amount,
                        contract=contract,
                        )
                    amounts.append(amount)
        Amount.create([a._save_values for a in amounts])

    @classmethod
    def _calculate_methods(cls, product):
        methods = super(Contract, cls)._calculate_methods(product)
        if product.is_loan and not Transaction().context.get(
                '_force_calculate_prices', None):
            methods.remove(('contract', 'calculate_prices'))
        return methods

    def get_rebill_end_date(self):
        if not self.is_loan:
            return super(Contract, self).get_rebill_end_date()
        return max(utils.today(), self.start_date)


class PremiumAmount(model.CoopSQL, model.CoopView):
    'Premium Amount'
    __name__ = 'contract.premium.amount'
    premium = fields.Many2One('contract.premium', 'Premium', select=True,
        ondelete='CASCADE')
    # XXX duplicate with premium but it is not possible with current design to
    # search via premium
    contract = fields.Many2One('contract', 'Contract', select=False,
        ondelete='CASCADE', required=True)
    period_start = fields.Date('Period Start', select=True)
    period_end = fields.Date('Period End', select=True)
    start = fields.Date('Start')
    end = fields.Date('End')
    amount = fields.Numeric('Amount')
    tax_amount = fields.Numeric('Tax Amount')
    covered_element = fields.Function(
        fields.Many2One('contract.covered_element', 'Covered element'),
        'get_covered_element')
    type_ = fields.Function(
        fields.Many2One('ir.model', 'Type'),
        'get_type')
    loan = fields.Function(
        fields.Many2One('loan', 'Loan'),
        'get_loan')

    @classmethod
    def __register__(cls, module_name):
        super(PremiumAmount, cls).__register__(module_name)

        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor()
        table = TableHandler(cursor, cls, module_name)

        # These indexes optimizes invoice generation
        # And certainly other coog services
        table.index_action('contract', 'remove')
        table.index_action(['contract', 'period_start', 'period_end'], 'add')

    def get_type(self, name=None):
        if self.premium:
            model, = Pool().get('ir.model').search(
                [('model', '=', self.premium.parent.__name__)])
            return model.id

    def get_covered_element(self, name=None):
        if self.premium:
            covered_element = getattr(self.premium.parent, 'covered_element',
                None)
            if covered_element:
                return covered_element.id

    def get_loan(self, name=None):
        if self.premium:
            loan = getattr(self.premium, 'loan', None)
            if loan:
                return loan.id


class PremiumAmountPerPeriod(model.CoopSQL, model.CoopView):
    'Premium Amount per Period'
    __name__ = 'contract.premium.amount.per_period'
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    amount = fields.Numeric('Amount')
    fees = fields.Numeric('Fees')
    untaxed_amount = fields.Numeric('Untaxed Amount')
    tax_amount = fields.Numeric('Tax Amount')
    total = fields.Numeric('Total')
    period_start = fields.Date('Period Start')
    period_end = fields.Date('Period End')
    premium_amounts = fields.Function(
        fields.One2Many('contract.premium.amount', None, 'Premium Amounts'),
        'get_premium_amounts')

    @classmethod
    def __setup__(cls):
        super(PremiumAmountPerPeriod, cls).__setup__()
        cls._order = [('contract', 'ASC'), ('period_start', 'ASC')]

    @classmethod
    def _export_light(cls):
        return super(PremiumAmountPerPeriod, cls)._export_light() | {
            'contract'}

    @staticmethod
    def table_query():
        pool = Pool()
        PremiumAmount = pool.get('contract.premium.amount')
        premium_amount = PremiumAmount.__table__()
        Premium = pool.get('contract.premium')
        premium = Premium.__table__()

        where_clause = None
        if 'contracts' in Transaction().context:
            where_clause = (premium_amount.contract.in_(
                    Transaction().context.get('contracts')))

        return premium_amount.join(premium, 'LEFT',
            condition=premium_amount.premium == premium.id
            ).select(
                Max(premium_amount.id).as_('id'),
                Literal(0).as_('create_uid'),
                Literal(0).as_('create_date'),
                Literal(0).as_('write_uid'),
                Literal(0).as_('write_date'),
                premium_amount.contract.as_('contract'),
                Sum(Case((~premium.rated_entity.ilike(
                                'account.fee,%'),
                            premium_amount.amount),  # NOQA
                        else_=0)).as_('amount'),
                Sum(Case((premium.rated_entity.ilike(
                                'account.fee,%'),
                            premium_amount.amount),  # NOQA
                        else_=0)).as_('fees'),
                Sum(premium_amount.amount).as_('untaxed_amount'),
                Round(Sum(premium_amount.tax_amount), 2).as_('tax_amount'),
                Round(Sum(premium_amount.amount + premium_amount.tax_amount),
                    2).as_('total'),
                premium_amount.period_start.as_('period_start'),
                premium_amount.period_end.as_('period_end'),
                where=where_clause,
                group_by=[
                    premium_amount.contract,
                    premium_amount.period_start,
                    premium_amount.period_end,
                    ])

    @classmethod
    def read(cls, ids, fields_names=None):
        if 'contracts' not in Transaction().context and ids:
            cursor = Transaction().cursor
            premium = Pool().get('contract.premium.amount').__table__()
            cursor.execute(*premium.select(premium.contract,
                    where=premium.id.in_(ids), order_by=[premium.contract]))
            contracts = list(set(cursor.fetchall()))
            with Transaction().set_context(contracts=contracts):
                return super(PremiumAmountPerPeriod, cls).read(ids,
                    fields_names)
        return super(PremiumAmountPerPeriod, cls).read(ids, fields_names)

    def get_premium_amounts(self, name):
        pool = Pool()
        PremiumAmount = pool.get('contract.premium.amount')
        premium_amounts = PremiumAmount.search([
                ('contract', '=', self.contract),
                ('period_start', '=', self.period_start),
                ('period_end', '=', self.period_end),
                ])
        return [p.id for p in premium_amounts]


class Loan:
    __name__ = 'loan'

    average_premium_rate = fields.Function(
        fields.Numeric('Average Premium Rate', digits=(6, 4)),
        'get_average_premium_rate')
    base_premium_amount = fields.Function(
        fields.Numeric('Base Premium Amount', digits=(16, 2)),
        'get_average_premium_rate')

    @classmethod
    def get_average_premium_rate(cls, loans, names, contract=None):
        if not contract:
            contract_id = Transaction().context.get('contract', None)
            if contract_id:
                contract = Pool().get('contract')(contract_id)
            else:
                return {name: {x.id: None for x in loans} for name in names}
        field_values = {'average_premium_rate': {}, 'base_premium_amount': {}}
        rule = contract.product.average_loan_premium_rule
        for loan in loans:
            vals = rule.calculate_average_premium_for_contract(loan, contract)
            field_values['base_premium_amount'][loan.id] = vals[0] or 0
            field_values['average_premium_rate'][loan.id] = vals[1] or 0
        return field_values


class AveragePremiumRateLoanDisplayer(model.CoopView):
    'Average Premium Rate Loan Displayer'

    __name__ = 'loan.average_premium_rate.loan_displayer'

    average_premium_rate = fields.Numeric('Average Premium Rate',
        digits=(6, 4))
    base_premium_amount = fields.Numeric('Base Premium Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits')
    current_loan_shares = fields.One2Many(
        'loan.average_premium_rate.loan_displayer', None,
        'Current Loan Shares')
    currency_symbol = fields.Char('Currency Symbol')
    name = fields.Char('Name')


class DisplayLoanAveragePremiumValues(model.CoopView):
    'Display Loan Average Premium Values'

    __name__ = 'loan.average_premium_rate.display.values'

    loan_displayers = fields.One2Many(
        'loan.average_premium_rate.loan_displayer', None, 'Loans',
        readonly=True)


class DisplayLoanAveragePremium(Wizard):
    'Display Loan Average Premium'

    __name__ = 'loan.average_premium_rate.display'

    start_state = 'display_loans'
    display_loans = StateView('loan.average_premium_rate.display.values',
        'contract_loan_invoice.display_average_premium_values_view_form', [
            Button('Cancel', 'end', 'tryton-cancel')])

    def default_display_loans(self, name):
        if not Transaction().context.get('active_model') == 'contract':
            return {}
        contract_id = Transaction().context.get('active_id', None)
        if contract_id is None:
            return {}
        contract = Pool().get('contract')(contract_id)
        with Transaction().set_context(contract=contract_id):
            return {'loan_displayers': [{
                        'name': x.rec_name,
                        'average_premium_rate': x.average_premium_rate,
                        'base_premium_amount': x.base_premium_amount,
                        'currency_digits': x.currency_digits,
                        'currency_symbol': x.currency_symbol,
                        'current_loan_shares': [{
                                'name': y.option.rec_name,
                                'average_premium_rate': y.average_premium_rate,
                                'base_premium_amount': y.base_premium_amount,
                                'currency_digits': x.currency_digits,
                                'currency_symbol': x.currency_symbol,
                                'current_loan_shares': [],
                                } for y in x.current_loan_shares],
                        } for x in contract.used_loans],
                }

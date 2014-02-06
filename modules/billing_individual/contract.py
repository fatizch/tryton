from itertools import repeat, izip, chain
from decimal import Decimal
import datetime
from collections import defaultdict
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Date

from trytond.modules.cog_utils import model, fields, utils, coop_date
from trytond.modules.contract_insurance.contract import IS_PARTY


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'Option',
    'CoveredElement',
    'CoveredData',
    ]


class Contract:
    __name__ = 'contract'

    billing_datas = fields.One2Many('contract.billing.data', 'contract',
        'Billing Datas')
    use_prices = fields.Function(
        fields.Boolean('Use Prices', states={'invisible': True}),
        'get_use_prices')
    next_billing_date = fields.Date('Next Billing Date',
        states={'invisible': ~Eval('use_prices')})
    prices = fields.One2Many(
        'contract.billing.premium', 'contract', 'Prices',
        states={'invisible': ~Eval('use_prices')},
        order=[('start_date', 'ASC'), ('on_object', 'ASC')])
    billing_periods = fields.One2Many('contract.billing.period', 'contract',
        'Billing Periods')
    receivable_lines = fields.Function(
        fields.One2Many('account.move.line', None, 'Receivable Lines',
            depends=['display_all_lines', 'id'],
            domain=[('account.kind', '=', 'receivable'),
                ('reconciliation', '=', None),
                ('origin', '=', ('contract', Eval('id', 0))),
                If(~Eval('display_all_lines'),
                    ('maturity_date', '<=',
                        Eval('context', {}).get(
                            'client_defined_date', Date())),
                    ())],
            loading='lazy'),
        'on_change_with_receivable_lines')
    receivable_today = fields.Function(fields.Numeric('Receivable Today'),
            'get_receivable_today', searcher='search_receivable_today')
    last_bill = fields.Function(
        fields.One2Many('account.move', None, 'Last Bill'),
        'get_last_bill')
    display_all_lines = fields.Function(
        fields.Boolean('Display all lines'),
        'get_display_all_lines', 'setter_void')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_prices': {'invisible': ~Eval('use_prices')},
                })

    @fields.depends('display_all_lines', 'id')
    def on_change_with_receivable_lines(self, name=None):
        return map(lambda x: x.id, utils.get_domain_instances(self,
            'receivable_lines'))

    def get_display_all_lines(self, name):
        return False

    def get_name_for_billing(self):
        return self.offered.name + ' - Base Price'

    def new_billing_data(self):
        return utils.instanciate_relation(self, 'billing_datas')

    def init_from_offered(self, offered, start_date=None, end_date=None):
        res = super(Contract, self).init_from_offered(offered, start_date,
            end_date)
        self.init_billing_data()
        return res

    def init_billing_data(self):
        if utils.is_none(self, 'billing_datas'):
            bm = self.new_billing_data()
            bm.init_from_contract(self, self.start_date)
            self.billing_datas = [bm]
            bm.save()
        if utils.is_none(self, 'next_billing_date'):
            self.next_billing_date = self.start_date

    def get_billing_data(self, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        for manager in self.billing_datas:
            if (manager.start_date <= date
                    and (manager.end_date is None
                        or manager.end_date >= date)):
                return manager

    def get_billing_period_at_date(self, date):
        Period = Pool().get('contract.billing.period')
        candidates = Period.search([
                ('contract', '=', self.id), ('start_date', '<=', date),
                ('end_date', '>=', date)])
        if not candidates:
            return None
        elif len(candidates) > 1:
            raise Exception('Multiple billing periods found for date %s' %
                date)
        return (candidates[0].start_date, candidates[0].end_date)

    def next_billing_period(self):
        start_date = self.next_billing_date
        last_date = coop_date.add_day(self.start_date, -1)
        if not utils.is_none(self, 'billing_periods'):
            for period in self.billing_periods:
                if (start_date >= period.start_date and (
                        not period.end_date or period.end_date >= start_date)):
                    return (period.start_date, period.end_date)
            if period.end_date > last_date:
                last_date = period.end_date
        new_period_start = coop_date.add_day(last_date, 1)
        appliable_frequency = self.get_product_frequency(last_date)
        if appliable_frequency == 'one_shot':
            return (new_period_start, self.end_date)
        new_period_end = coop_date.add_frequency(appliable_frequency,
            last_date)
        if self.next_renewal_date:
            new_period_end = min(new_period_end, coop_date.add_day(
                self.next_renewal_date, -1))
        if self.end_date and new_period_end > self.end_date:
            return (new_period_start, self.end_date)
        return (new_period_start, new_period_end)

    @classmethod
    def get_price_line_model(cls):
        return cls._fields['prices'].model_name

    def get_product_frequency(self, at_date):
        res, errs = self.offered.get_result(
            'frequency', {
                'date': at_date,
                'appliable_conditions_date': self.appliable_conditions_date})
        if not errs:
            return res

    def store_prices(self, prices):
        if not prices:
            return
        Premium = Pool().get(self.get_price_line_model())
        dates = list(set([elem.start_date for elem in prices]))
        dates.sort()
        result_prices = []
        to_delete = []
        oldest = []
        if hasattr(self, 'prices') and self.prices:
            result_prices = list(filter(lambda x: x.start_date < dates[0],
                self.prices))
            to_delete = list(filter(lambda x: x.start_date >= dates[0],
                self.prices))
            by_dates = {}
            max_date = None
            for elem in result_prices:
                by_dates.setdefault(elem.start_date, []).append(elem)
                max_date = max_date if (
                    max_date and max_date > elem.start_date) \
                    else elem.start_date
            oldest = by_dates[max_date] if max_date else []
        for price in prices:
            price_line = Premium()
            price_line.init_from_result_line(price, True)
            try:
                price_line.end_date = dates[dates.index(price_line.start_date)
                    + 1] + datetime.timedelta(days=-1)
            except IndexError:
                pass
            result_prices.append(price_line)
        for elem in oldest:
            elem.end_date = coop_date.add_day(dates[0], -1)
            elem.save()
        if to_delete:
            Premium.delete(to_delete)
        self.prices = result_prices
        self.save()

    @classmethod
    @model.CoopView.button
    def button_calculate_prices(cls, contracts):
        for contract in contracts:
            contract.calculate_prices()

    def calculate_prices(self):
        prices, errs = self.calculate_prices_between_dates()
        if errs:
            return False, errs
        self.store_prices(prices)
        return True, ()

    def create_price_list(self, start_date, end_date):
        res = []
        for price_line in self.prices:
            if start_date > price_line.start_date:
                start = start_date
            else:
                start = price_line.start_date
            if not price_line.end_date:
                end = end_date
            elif end_date < price_line.end_date:
                end = end_date
            else:
                end = price_line.end_date
            if start <= end and price_line.amount:
                res.append(((start, end), price_line))
        return res

    @staticmethod
    def get_journal():
        Journal = Pool().get('account.journal')
        journal, = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        return journal

    def get_or_create_billing_period(self, period):
        BillingPeriod = Pool().get('contract.billing.period')
        for billing_period in self.billing_periods \
                if hasattr(self, 'billing_periods') else []:
            if (billing_period.start_date, billing_period.end_date) == period:
                break
        else:
            billing_period = BillingPeriod(contract=self)
            billing_period.start_date, billing_period.end_date = period
            billing_period.save()
        return billing_period

    def init_billing_work_set(self):
        Line = Pool().get('account.move.line')
        return {
            'lines': defaultdict(lambda: Line(credit=0, debit=0)),
            'total_amount': 0,
            'taxes': defaultdict(
                lambda: {'amount': 0, 'base': 0, 'to_recalculate': False}),
            'fees': defaultdict(
                lambda: {'amount': 0, 'base': 0, 'to_recalculate': False}),
            }

    def create_billing_move(self, work_set):
        Move = Pool().get('account.move')
        Period = Pool().get('account.period')

        period_id = Period.find(self.company.id, date=work_set['period'][0])
        move = Move(
            journal=self.get_journal(),
            period=period_id,
            date=work_set['period'][0],
            origin=utils.convert_to_reference(self),
            billing_period=work_set['billing_period'],
            )
        return move

    def calculate_base_lines(self, work_set):
        for period, price_line in work_set['price_lines']:
            price_line.calculate_bill_contribution(work_set, period)

    def calculate_final_taxes_and_fees(self, work_set):
        for type_, data in chain(
                izip(repeat('tax'), work_set['taxes'].itervalues()),
                izip(repeat('fee'), work_set['fees'].itervalues())):
            account = data['object'].get_account_for_billing()
            line = work_set['lines'][(data['object'], account)]
            line.party = self.subscriber
            line.account = account
            if data['to_recalculate']:
                good_version = data['object'].get_version_at_date(
                    work_set['period'][0])
                amount = getattr(good_version,
                    'apply_%s' % type_)(data['base'])
            else:
                amount = data['amount']
            line.second_origin = data['object']
            line.credit = work_set['currency'].round(amount)
            work_set['total_amount'] += line.credit

    def calculate_billing_fees(self, work_set):
        if not work_set['payment_term']:
            return
        for fee_desc in work_set['payment_term'].appliable_fees:
            fee_line = work_set['fees'][fee_desc.id]
            fee_line['object'] = fee_desc
            fee_line['to_recalculate'] = True
            fee_line['amount'] = 0
            fee_line['base'] = work_set['total_amount']

    def compensate_existing_moves_on_period(self, work_set):
        if not work_set['billing_period'].moves:
            return
        Move = Pool().get('account.move')
        for old_move in work_set['billing_period'].moves:
            if old_move.state == 'draft':
                continue
            for old_line in old_move.lines:
                if old_line.account == self.subscriber.account_receivable:
                    continue
                line = work_set['lines'][
                    (old_line.second_origin, old_line.account)]
                line.second_origin = old_line.second_origin
                line.account = old_line.account
                if old_line.credit:
                    line.credit -= old_line.credit
                    work_set['total_amount'] -= old_line.credit
                else:
                    line.credit += old_line.debit
                    work_set['total_amount'] += old_line.debit
        Move.delete([
                x for x in work_set['billing_period'].moves
                if x.state == 'draft'])

    def apply_payment_term(self, work_set):
        Line = Pool().get('account.move.line')
        Date = Pool().get('ir.date')
        for line in work_set['lines'].itervalues():
            if line.credit < 0:
                line.credit, line.debit = 0, -line.credit

        if work_set['total_amount'] >= 0 and work_set['payment_term']:
            term_lines = work_set['payment_term'].compute(
                work_set['period'][0], work_set['period'][1],
                work_set['total_amount'], work_set['currency'],
                work_set['payment_date'])
        else:
            term_lines = [(Date.today(), work_set['currency'].round(
                        work_set['total_amount']))]
        counterparts = []
        for term_date, amount in term_lines:
            counterpart = Line()
            if amount >= 0:
                counterpart.credit = 0
                counterpart.debit = amount
            else:
                counterpart.credit = - amount
                counterpart.debit = 0
            counterpart.account = self.subscriber.account_receivable
            counterpart.party = self.subscriber
            counterpart.maturity_date = term_date
            counterparts.append(counterpart)
        work_set['counterparts'] = counterparts

    def bill(self, *period):
        # Performs billing operations on the contract. It is possible to force
        # the period to work on

        # Get the period if it is not provided
        if not period:
            period = self.next_billing_period()
        if not period:
            return

        # Get the billing_data and the billing period
        self.init_billing_data()
        billing_data = self.get_billing_data(period[0])
        assert billing_data, 'Missing Billing Data'
        billing_period = self.get_or_create_billing_period(period)

        # Get the appliable prices ont the period. This is a list of tuples
        # of the form ((start_date, end_date), Premium)
        price_lines = self.create_price_list(*period)

        # Init the work_set which will be used
        currency = self.get_currency()
        work_set = self.init_billing_work_set()
        work_set['price_lines'] = price_lines
        work_set['payment_date'] = billing_data.get_payment_date()
        work_set['payment_method'] = billing_data.payment_method
        if work_set['payment_method']:
            work_set['payment_term'] = work_set['payment_method'].get_rule()
        else:
            work_set['payment_term'] = None
        work_set['period'] = period
        work_set['currency'] = currency
        work_set['billing_period'] = billing_period
        work_set['move'] = self.create_billing_move(work_set)

        # Build the basic lines which represents the total amount due on the
        # period. Those lines include product / coverage rates, taxes and fees
        self.calculate_base_lines(work_set)

        # Add billing fees if needed
        self.calculate_billing_fees(work_set)

        # Calculate final value of taxes and fees. The later the better to
        # avoid rounding problems. Some may have been already calculated in the
        # prices lines for complexity reasons
        self.calculate_final_taxes_and_fees(work_set)

        # Compensate for previous moves on the period. The current lines
        # account for all must be paid on the period, we need to remove what
        # has already been paid (or at least billed)
        self.compensate_existing_moves_on_period(work_set)

        # Schedule the payments depending on the chosen rule
        self.apply_payment_term(work_set)

        work_set['move'].lines = work_set['lines'].values() + \
            work_set['counterparts']
        if work_set['total_amount'] > 0:
            work_set['move'].save()
            return work_set['move']
        else:
            return

    def bill_and_post(self, post=True):
        Move = Pool().get('account.move')
        Move.delete(Move.search([
                ('origin', '=', utils.convert_to_reference(self)),
                ('state', '=', 'draft'),
                ]))
        Transaction().cursor.commit()
        move = self.bill()
        if move and post:
            self.next_billing_date = coop_date.add_day(
                move.billing_period.end_date, 1)
            self.save()
            if not move.lines:
                Move.delete([move])
            else:
                Move.post([move])

    def generate_first_bill(self):
        if self.next_billing_date:
            self.next_billing_date = self.start_date
        self.bill_and_post(post=False)

    def calculate_price_at_date(self, date):
        cur_dict = {
            'date': date,
            'appliable_conditions_date': self.appliable_conditions_date}
        self.init_dict_for_rule_engine(cur_dict)
        prices, errs = self.offered.get_result('total_price', cur_dict)
        return (prices, errs)

    def calculate_prices_between_dates(self, start=None, end=None):
        if not start:
            start = self.start_date
        prices = []
        errs = []
        dates = self.get_dates()
        dates = utils.limit_dates(dates, self.start_date)
        for cur_date in dates:
            price, err = self.calculate_price_at_date(cur_date)
            if price:
                prices.extend(price)
            errs += err
        return prices, errs

    def get_last_bill(self, name):
        Move = Pool().get('account.move')
        try:
            result = [Move.search(
                [('origin', '=', utils.convert_to_reference(self))])[0].id]
            return result
        except:
            return []

    def get_total_price_at_date(self, at_date):
        return sum(map(lambda x: x.amount, filter(
            lambda x: x.start_date <= at_date and (
                not x.end_date or x.end_date >= at_date), self.prices)))

    def finalize_contract(self):
        super(Contract, self).finalize_contract()
        self.bill_and_post()

    def renew(self):
        res = super(Contract, self).renew()
        if not res:
            return res
        self.bill_and_post()
        return True

    def re_bill_from_date(self, at_date):
        '''Recalculate a new bill for a period when a modifiction has occured
        in the past and the previous bills already posted may be false'''
        if self.next_billing_date:
            self.next_billing_date = at_date
        self.bill_and_post()

    def temp_endorsment_re_bill(self):
        #TODO :Temporay while we don't have the endorsement date
        self.re_bill_from_date(self.start_date)

    # From account => party
    @classmethod
    def get_receivable_today(cls, contracts, name):
        res = {}
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        res = dict((p.id, Decimal('0.0')) for p in contracts)

        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        user = User(user_id)
        if not user.company:
            return res

        move_line = MoveLine.__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()
        line_query, _ = MoveLine.query_get(move_line)

        query_table = move.join(move_line,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))
        today_query = (move_line.maturity_date <= Date.today()) | (
            move_line.maturity_date == None)
        good_moves_query = move.id.in_(move.select(move.id, where=(
                    move.origin.in_(
                        ['contract,%s' % x.id for x in contracts]))))

        cursor.execute(*query_table.select(move.origin, Sum(
                Coalesce(move_line.debit, 0) - Coalesce(move_line.credit, 0)),
                where=(account.active)
                & (account.kind == 'receivable')
                & good_moves_query
                & (move_line.reconciliation == None)
                & line_query
                & today_query
                & (account.company == user.company.id),
                group_by=(move.origin)))
        for contract_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[int(contract_id.split(',')[1])] = sum
        return res

    @classmethod
    def search_receivable_today(cls, name, clause):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Company = pool.get('company.company')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        if name not in ('receivable', 'payable',
                'receivable_today', 'payable_today'):
            raise Exception('Bad argument')

        company_id = None
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        user = User(user_id)
        if Transaction().context.get('company'):
            child_companies = Company.search([
                    ('parent', 'child_of', [user.main_company.id]),
                    ])
            if Transaction().context['company'] in child_companies:
                company_id = Transaction().context['company']

        if not company_id:
            if user.company:
                company_id = user.company.id
            elif user.main_company:
                company_id = user.main_company.id

        if not company_id:
            return []

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        move_line = MoveLine.__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()
        line_query, _ = MoveLine.query_get(move_line)

        query_table = move.join(move_line,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))
        today_query = (move_line.maturity_date <= Date.today()) | (
            move_line.maturity_date == None)

        code = name
        today_query = True
        if name in ('receivable_today', 'payable_today'):
            code = name[:-6]
            today_query = (move_line.maturity_date <= Date.today()) | (
                move_line.maturity_date == None)

        cursor.execute(*query_table.select(move.contract,
                where=(account.active)
                & (account.kind == code)
                & (move_line.reconciliation == None)
                & line_query
                & today_query
                & (account.company == Company(company_id)),
                group_by=(move_line.party),
                having=Operator(Sum(
                        Coalesce(move_line.debit, 0) -
                        Coalesce(move_line.credit, 0)),
                    getattr(cls, name).sql_format(value))))

        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Contract, cls).get_var_names_for_full_extract()
        res.extend(['billing_datas'])
        return res

    def get_use_prices(self, name):
        if not self.offered:
            return False
        for rules in self.offered.premium_rules:
            return True
        for option in self.options:
            if option.offered.premium_rules:
                return True
        return False


class Option:
    __name__ = 'contract.option'

    def get_name_for_billing(self):
        return self.option.name + ' - Base Price'


class CoveredElement:
    __name__ = 'contract.covered_element'

    subscriber = fields.Function(
        fields.Many2One('party.party', 'Subscriber'),
        'get_subscriber_id')
    indemnification_bank_account = fields.Many2One('bank.account',
        'Indemnification Bank Account',
        states={'invisible': ~Eval('is_person')},
        depends=['item_kind', 'party', 'subscriber'],
        domain=[
            ['OR',
                ('owners', '=', Eval('subscriber')),
                If(IS_PARTY, ('owners', '=', Eval('party', 0)), ())]],
        ondelete='RESTRICT')

    def get_name_for_billing(self):
        return self.get_rec_name('billing')

    def get_subscriber_id(self, name):
        return self.main_contract.subscriber.id


class CoveredData:
    __name__ = 'contract.covered_data'

    def get_name_for_billing(self):
        return self.covered_element.get_name_for_billing()

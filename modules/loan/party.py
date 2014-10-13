import copy
import datetime

from decimal import Decimal
from sql.aggregate import Max
from sql import Literal
from sql.conditionals import Coalesce
from collections import defaultdict

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, PYSONEncoder
from trytond.wizard import Wizard, StateView, Button

from trytond.modules.cog_utils import fields, model, coop_string, UnionMixin

__metaclass__ = PoolMeta
__all__ = [
    'SynthesisMenuLoan',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    'DisplayInsuredOutstandingLoanBalance',
    'InsuredOutstandingLoanBalanceView',
    'InsuredOutstandingLoanBalanceLineView',
    'InsuredOutstandingLoanBalanceSelectDate',
    ]


class SynthesisMenuLoan(model.CoopSQL):
    'Party Synthesis Menu Loan'
    __name__ = 'party.synthesis.menu.loan'
    name = fields.Char('Loans')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        LoanSynthesis = pool.get('party.synthesis.menu.loan')
        party = pool.get('party.party').__table__()
        loan_party = pool.get('loan-party').__table__()
        query_table = party.join(loan_party, 'LEFT OUTER',
            condition=(party.id == loan_party.party))
        return query_table.select(
            party.id,
            Max(loan_party.create_uid).as_('create_uid'),
            Max(loan_party.create_date).as_('create_date'),
            Max(loan_party.write_uid).as_('write_uid'),
            Max(loan_party.write_date).as_('write_date'),
            Literal(coop_string.translate_label(LoanSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'loan-interest'

    def get_rec_name(self, name):
        LoanSynthesis = Pool().get('party.synthesis.menu.loan')
        return coop_string.translate_label(LoanSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
            'party.synthesis.menu.loan',
            'loan-party',
            ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.loan':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'loan-party':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = 'party.synthesis.menu.loan'
                return union_field
            elif name == 'name':
                return Model._fields['loan']
        return union_field

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.loan':
            res = 5
        return res


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if (Model.__name__ != 'party.synthesis.menu.loan' and
                Model.__name__ != 'loan-party'):
            return super(SynthesisMenuOpen, self).get_action(record)
        if Model.__name__ == 'party.synthesis.menu.loan':
            domain = PYSONEncoder().encode([('parties', '=', record.id)])
            actions = {
                'res_model': 'loan',
                'pyson_domain': domain,
                'views': [(None, 'tree'), (None, 'form')]
            }
        elif Model.__name__ == 'loan-party':
            actions = {
                'res_model': 'loan',
                'views': [(None, 'form')],
                'res_id': record.loan.id
            }
        return actions


class DisplayInsuredOutstandingLoanBalance(Wizard):
    'Display Insured Outstanding Loan Balance Wizard'

    __name__ = 'party.display_insured_outstanding_loan_balance'

    start_state = 'select_date'
    select_date = StateView(
        'party.display_insured_outstanding_loan_balance.select_date',
        'loan.display_insured_outstanding_loan_balance_select_date_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'insured_outstanding_loan_balance_view',
                'tryton-go-next', default=True),
        ])
    insured_outstanding_loan_balance_view = StateView(
        'party.display_insured_outstanding_loan_balance.view',
        'loan.display_insured_outstanding_loan_balance_view_form', [
            Button('Previous', 'select_date', 'tryton-go-previous'),
            Button('Ok', 'end', 'tryton-go-next', default=True),
            ])

    def default_select_date(self, name):
        if self.select_date._default_values:
            return self.select_date._default_values
        pool = Pool()
        Party = pool.get('party.party')
        selected_party = Party(Transaction().context.get('active_id'))
        Company = pool.get('company.company')
        company = Company(Transaction().context.get('company'))
        currencies = []
        default_currency = None
        for contract in selected_party.contracts:
            for loan in contract.loans:
                currencies.append(loan.currency.id)
                if loan.currency == company.currency:
                    default_currency = loan.currency.id
        if not default_currency and currencies:
            default_currency = currencies[0].id
        return {
            'date': datetime.date.today(),
            'party': selected_party.id,
            'possible_currencies': currencies,
            'currency': default_currency,
            }

    def get_insured_outstanding_loan_balances(self, party, date, currency):
        cursor = Transaction().cursor
        pool = Pool()
        Loan = pool.get('loan')
        Insurer = pool.get('insurer')
        Coverage = pool.get('offered.option.description')

        contract = pool.get('contract').__table__()
        history = pool.get('contract.activation_history').__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        option = pool.get('contract.option').__table__()
        coverage = pool.get('offered.option.description').__table__()
        loan_share = pool.get('loan.share').__table__()
        loan = Loan.__table__()
        insurer = Insurer.__table__()

        query_table = covered_element.join(option, condition=(
                    (option.covered_element == covered_element.id)
                    & (option.status == 'active')
                    & (covered_element.party == party.id)
                    & (Coalesce(option.start_date, datetime.date.min) <= date)
                    & (((option.manual_end_date != None) &
                            (option.manual_end_date >= date)) |  # NOQA
                        ((option.manual_end_date == None) &
                            (Coalesce(option.automatic_end_date,
                                datetime.date.max) >= date))))
            ).join(coverage, condition=(
                    option.coverage == coverage.id)
            ).join(loan_share, condition=(loan_share.option == option.id)
            ).join(loan, condition=(
                    (loan_share.loan == loan.id)
                    & (loan.currency == currency.id))
            ).join(contract, condition=(
                    covered_element.contract == contract.id)
            ).join(history, condition=(
                    (history.contract == contract.id)
                    & (history.start_date <= date)
                    & (history.end_date >= date)))

        cursor.execute(*query_table.select(coverage.insurer, loan.id,
                loan_share.share, coverage.insurance_kind, coverage.id,
                order_by=(coverage.insurer, coverage.insurance_kind)))

        translated = {}
        aggregate_amounts = defaultdict(
            lambda: defaultdict(lambda: Decimal(0)))
        for insurer, loan_id, share, insurance_kind, coverage_id in (
                cursor.fetchall()):
            loan = Loan(loan_id)
            aggregate_amounts[insurer][insurance_kind] += currency.round(
                share * (loan.get_outstanding_loan_balance(
                        at_date=date) or 0))
            if insurance_kind not in translated:
                translated[insurance_kind] = (
                    coop_string.translate_value(Coverage(coverage_id),
                        'insurance_kind'))

        res = []
        for insurer_id, values in aggregate_amounts.iteritems():
            insurer = Insurer(insurer_id)
            max_amount, childs = 0, []
            for insurance_kind, amount in values.iteritems():
                childs.append({
                        'name': translated[insurance_kind],
                        'currency_symbol': currency.symbol,
                        'currency_digits': currency.digits,
                        'childs': None,
                        'amount': amount,
                        })
                max_amount = max(amount, max_amount)
            res.append({
                    'name': insurer.rec_name,
                    'currency_symbol': currency.symbol,
                    'currency_digits': currency.digits,
                    'childs': childs,
                    'amount': max_amount,
                    })

        total = [{
                'name': 'Total',
                'currency_symbol': currency.symbol,
                'currency_digits': currency.digits,
                'childs': None,
                'amount': sum([x['amount'] for x in res]),
                }]

        return total + res

    def default_insured_outstanding_loan_balance_view(self, name):
        party = self.select_date.party
        date = self.select_date.date
        currency = self.select_date.currency
        return {
            'insurers': self.get_insured_outstanding_loan_balances(
                party, date, currency),
            'date': self.select_date.date,
            }


class InsuredOutstandingLoanBalanceView(model.CoopView):
    'Insured Outstanding Loan Balance View'

    __name__ = 'party.display_insured_outstanding_loan_balance.view'

    insurers = fields.One2Many(
        'party.display_insured_outstanding_loan_balance.line_view',
        None, 'Loan Insurers', readonly=True)
    date = fields.Date('Date')


class InsuredOutstandingLoanBalanceLineView(model.CoopView):
    'Insured Outstanding Loan Balance Line View'

    __name__ = 'party.display_insured_outstanding_loan_balance.line_view'

    name = fields.Char('Name')
    amount = fields.Numeric('Insured Outstanding Loan Balance',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_symbol = fields.Char('Symbol')
    currency_digits = fields.Integer('Currency Digits')
    childs = fields.One2Many(
            'party.display_insured_outstanding_loan_balance.line_view',
            None, 'Childs')
    insurers = fields.Char('Loan Insurers', states={'invisible': True})


class InsuredOutstandingLoanBalanceSelectDate(model.CoopSQL, model.CoopView):
    'Date selector for insured outstanding loan balance display'

    __name__ = 'party.display_insured_outstanding_loan_balance.select_date'

    date = fields.Date('Date', required=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency',
            required=True, depends=['possible_currencies'],
            domain=[('id', 'in', Eval('possible_currencies'))])
    possible_currencies = fields.Many2Many('currency.currency',
             None, None, 'Possible Currencies')

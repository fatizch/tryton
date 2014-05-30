from decimal import Decimal
from sql.aggregate import Max
from collections import defaultdict

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'Insurer',
    ]


class Party:
    __name__ = 'party.party'

    loan_insurers = fields.Function(
        fields.One2Many('insurer', None, 'Loan Insurers',
            context={'party': Eval('id', '')}, depends=['id']),
        'getter_loan_insurers')

    @classmethod
    def getter_loan_insurers(cls, parties, name):
        cursor = Transaction().cursor
        pool = Pool()

        party = cls.__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        option = pool.get('contract.option').__table__()
        coverage = pool.get('offered.option.description').__table__()

        query_table = covered_element.join(party, condition=(
                covered_element.party.in_([x.id for x in parties]))
            ).join(option, condition=(
                    option.covered_element == covered_element.id)
            ).join(coverage, condition=(option.coverage == coverage.id))

        cursor.execute(*query_table.select(party.id, coverage.insurer))

        result = defaultdict(list)
        for party_id, insurer in cursor.fetchall():
            result[party_id].append(insurer)

        return result


class Insurer:
    __name__ = 'insurer'

    total_outstanding_loan_balance = fields.Function(
        fields.Numeric('Total Loan Outstanding Capital'),
        'get_total_outstanding_loan_balance')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'getter_currency_symbol')

    def getter_currency_symbol(self, name):
        Company = Pool().get('company.company')
        return Company(Transaction().context.get('company')).currency.symbol

    @classmethod
    def get_total_outstanding_loan_balance(cls, insurers, name):
        party_id = Transaction().context.get('party', None)
        if party_id is None:
            return 0
        cursor = Transaction().cursor
        pool = Pool()
        today = pool.get('ir.date').today()
        Currency = pool.get('currency.currency')
        Company = pool.get('company.company')

        party = pool.get('party.party').__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        option = pool.get('contract.option').__table__()
        coverage = pool.get('offered.option.description').__table__()
        loan_share = pool.get('loan.share').__table__()
        payment = pool.get('loan.payment').__table__()
        loan = pool.get('loan').__table__()

        query_table = covered_element.join(party, condition=(
                covered_element.party == party_id)
            ).join(option, condition=(
                    option.covered_element == covered_element.id)
            ).join(coverage, condition=(
                (option.coverage == coverage.id)
                & (coverage.insurer.in_([x.id for x in insurers])))
            ).join(loan_share, condition=(loan_share.option == option.id)
            ).join(payment, condition=(
                (payment.loan == loan_share.loan)
                & (payment.start_date <= today))
            ).join(loan, condition=(loan.id == payment.loan))

        cursor.execute(*query_table.select(coverage.insurer, loan.id,
                Max(loan.currency),
                Max(payment.begin_balance) * Max(loan_share.share),
                group_by=[coverage.insurer, loan.id]))

        company = Company(Transaction().context.get('company'))
        target_currency = company.currency
        result = defaultdict(lambda: Decimal(0))
        for insurer, _, currency, outstanding_amount in cursor.fetchall():
            result[insurer] += Currency.compute(Currency(currency),
                outstanding_amount, target_currency)

        return result

import copy

from decimal import Decimal
from sql.aggregate import Max
from sql import Literal
from collections import defaultdict

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, PYSONEncoder
from trytond.wizard import Wizard

from trytond.modules.cog_utils import fields, model, coop_string, MergedMixin

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'Insurer',
    'SynthesisMenuLoan',
    'SynthesisMenu',
    'SynthesisMenuOpen',
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


class SynthesisMenuLoan(model.CoopSQL):
    'Party Synthesis Menu Loan'
    __name__ = 'party.synthesis.menu.loan'
    name = fields.Char('Loans')
    party = fields.Many2One('party.party', 'Party')

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


class SynthesisMenu(MergedMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def merged_models(cls):
        res = super(SynthesisMenu, cls).merged_models()
        res.extend([
            'party.synthesis.menu.loan',
            'loan-party',
            ])
        return res

    @classmethod
    def merged_field(cls, name, Model):
        merged_field = super(SynthesisMenu, cls).merged_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.loan':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'loan-party':
            if name == 'parent':
                merged_field = copy.deepcopy(Model._fields['party'])
                merged_field.model_name = 'party.synthesis.menu.loan'
                return merged_field
            elif name == 'name':
                return Model._fields['loan']
        return merged_field

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

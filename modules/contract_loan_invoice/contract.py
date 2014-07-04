import datetime
from collections import defaultdict

from sql import Cast
from sql.aggregate import Sum
from sql.operators import Concat

from trytond.wizard import Wizard, StateView, Button
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, utils, coop_date


__metaclass__ = PoolMeta
__all__ = [
    'LoanShare',
    'Premium',
    'Contract',
    'Loan',
    'DisplayLoanAveragePremiumValues',
    'DisplayLoanAveragePremium',
    ]


class LoanShare:
    __name__ = 'loan.share'

    average_premium_rate = fields.Function(
        fields.Numeric('Average Premium Rate', digits=(6, 4)),
        'get_average_premium_rate')

    def get_average_premium_rate(self, name):
        contract = self.option.covered_element.contract
        rule = contract.product.average_loan_premium_rule
        return rule.calculate_average_premium_for_option(contract, self)


class Premium:
    __name__ = 'contract.premium'

    loan = fields.Many2One('loan', 'Loan', select=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Premium, cls).__setup__()
        # Make sure premiums are properly ordered per loan
        cls._order.insert(0, ('loan', 'ASC'))

    def get_rec_name(self, name):
        rec_name = super(Premium, self).get_rec_name(name)
        if not self.loan:
            return rec_name
        return '[%s] %s' % (self.loan.number, rec_name)

    def same_value(self, other):
        return super(Premium, self).same_value(other) and (
            self.loan == other.loan)

    @classmethod
    def new_line(cls, line, start_date, end_date):
        result = super(Premium, cls).new_line(line, start_date, end_date)
        if 'loan' not in line:
            return result
        result.loan = line['loan']
        result.end = min(end_date or datetime.date.max,
            coop_date.add_day(line['loan'].end_date, -1))
        return result

    def get_description(self):
        description = super(Premium, self).get_description()
        if not self.loan:
            return description
        return '[%s] %s' % (self.loan.number, description)


class Contract:
    __name__ = 'contract'

    def calculate_premium_aggregates(self, start=None, end=None):
        cursor = Transaction().cursor
        pool = Pool()
        Premium = pool.get('contract.premium')
        invoice = pool.get('account.invoice').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        invoice_contract = pool.get('contract.invoice').__table__()
        premium = Premium.__table__()

        if start:
            date_clause = invoice_line.coverage_start >= start
        else:
            date_clause = None
        if end:
            if date_clause:
                date_clause &= (invoice_line.coverage_start <= end)

        query_table = invoice.join(invoice_contract, condition=(
                (invoice_contract.invoice == invoice.id)
                & (invoice.state.in_(['validated', 'posted', 'paid']))
                & (invoice_contract.contract == self.id))
            ).join(invoice_line, condition=(invoice_line.invoice == invoice.id)
            ).join(premium, condition=(
                Concat('contract.premium,', Cast(premium.id, 'VARCHAR'))
                == invoice_line.origin)
            )

        premium_fields = Premium.get_possible_parent_field()
        premium_parents = [getattr(premium, x) for x in premium_fields]
        premium_parents_models = dict([
                (x, pool.get(Premium._fields[x].model_name))
                for x in premium_fields])

        cursor.execute(*query_table.select(Sum(invoice_line.unit_price),
                premium.loan, *premium_parents, where=date_clause,
                group_by=[premium.loan] + premium_parents))
        per_contract_entity = defaultdict(lambda: defaultdict(lambda: 0))
        for elem in cursor.dictfetchall():
            parent = None
            for x in premium_fields:
                if not elem[x]:
                    continue
                parent = premium_parents_models[x](elem[x])
                break
            if parent:
                per_contract_entity[parent][elem['loan']] = elem['sum']

        cursor.execute(*query_table.select(premium.rated_entity, premium.loan,
                Sum(invoice_line.unit_price), where=date_clause,
                group_by=(premium.rated_entity, premium.loan)))
        per_offered_entity = defaultdict(lambda: defaultdict(lambda: 0))
        for elem in cursor.dictfetchall():
            parent = utils.convert_ref_to_obj(elem['rated_entity'])
            per_offered_entity[parent][elem['loan']] = elem['sum']

        def result_parser(kind, value=None, model_name='', loan_id=None):
            # Returns a function that can be used to browse the queries results
            # and aggregating them. It is possible to aggregate per model_name,
            # per a specific parent (eg. per covered_element), or per offered
            # entity (eg. offered coverage)
            assert kind in ('offered', 'contract')
            values = {}
            if kind == 'offered':
                values = per_offered_entity
            elif kind == 'contract':
                values = per_contract_entity
            if value:
                good_dict = values[value]
                if loan_id:
                    return good_dict[loan_id]
                return sum(good_dict.values())
            if model_name:
                result = sum([result_parser(kind, value=k, loan_id=loan_id)
                        for k, v in values.iteritems()
                        if k.__name__ == model_name])
                return result
            return values

        return result_parser

    def first_invoice(self):
        if not (self.is_loan and self.end_date):
            return super(Contract, self).first_invoice()
        ContractInvoice = Pool().get('contract.invoice')
        ContractInvoice.delete(self.invoices)
        self.invoice([self], self.end_date)


class Loan:
    __name__ = 'loan'

    average_premium_rate = fields.Function(
        fields.Numeric('Average Premium Rate', digits=(6, 4)),
        'get_average_premium_rate')

    def get_average_premium_rate(self, name, contract=None):
        if not contract:
            contract_id = Transaction().context.get('contract', None)
            if contract_id:
                contract = Pool().get('contract')(contract_id)
            else:
                return None
        rule = contract.product.average_loan_premium_rule
        return (rule.calculate_average_premium_for_contract(self, contract)
            if rule else None)


class DisplayLoanAveragePremiumValues(model.CoopView):
    'Display Loan Average Premium Values'

    __name__ = 'loan.average_premium_rate.display.values'

    loans = fields.One2Many('loan', None, 'Loans',
        context={'contract': Eval('contract')},
        depends=['contract'])
    contract = fields.Many2One('contract', 'Contract')


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
        return {'contract': contract_id,
            'loans': [x.id for x in contract.used_loans]}

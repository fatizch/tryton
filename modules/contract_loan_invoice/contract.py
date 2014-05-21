from sql import Cast
from sql.aggregate import Sum
from sql.operators import Concat

from trytond.wizard import Wizard, StateView, Button
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, utils


__metaclass__ = PoolMeta
__all__ = [
    'ContractOption',
    'LoanShare',
    'Premium',
    'Contract',
    'Loan',
    'DisplayLoanAveragePremiumValues',
    'DisplayLoanAveragePremium',
    ]


class ContractOption:
    __name__ = 'contract.option'

    def get_invoice_lines(self, start, end):
        lines = super(ContractOption, self).get_invoice_lines(start, end)
        for loan_share in self.loan_shares:
            lines.extend(loan_share.get_invoice_lines(start, end))
        return lines

    def get_premium_list(self, values):
        super(ContractOption, self).get_premium_list(values)
        for share in self.loan_shares:
            share.get_premium_list(values)


class LoanShare:
    __name__ = 'loan.share'

    premiums = fields.One2Many('contract.premium', 'loan_share', 'Premiums',
        order=[('rated_entity', 'ASC'), ('start', 'ASC')])
    average_premium_rate = fields.Function(
        fields.Numeric('Average Premium Rate', digits=(6, 4)),
        'get_average_premium_rate')

    def get_average_premium_rate(self, name):
        contract = self.option.covered_element.contract
        rule = contract.product.average_loan_premium_rule
        return rule.calculate_average_premium_for_option(contract, self)

    def get_invoice_lines(self, start, end):
        lines = []
        for premium in self.premiums:
            lines.extend(premium.get_invoice_lines(start, end))
        return lines

    def get_premium_list(self, values):
        values.extend(self.premiums)


class Premium:
    __name__ = 'contract.premium'

    loan_share = fields.Many2One('loan.share', 'Loan Share', select=True,
        ondelete='CASCADE')

    @classmethod
    def get_possible_parent_field(cls):
        result = super(Premium, cls).get_possible_parent_field()
        result.add('loan_share')
        return result

    def get_main_contract(self, name=None):
        if self.loan_share:
            return self.loan_share.option.parent_contract.id
        return super(Premium, self).get_main_contract(name)

    def calculate_rated_entity(self):
        rated_entity = super(Premium, self).calculate_rated_entity()
        if rated_entity:
            return rated_entity
        parent = self.get_parent()
        if parent.__name__ == 'loan.share':
            rated_entity = parent.option.coverage
        return rated_entity


class Contract:
    __name__ = 'contract'

    used_loans = fields.Function(
        fields.Many2Many('loan', None, None, 'Used Loans',
            context={'contract': Eval('id')}, depends=['id']),
        'get_used_loans')

    def get_used_loans(self, name):
        loans = set([share.loan
            for covered_element in self.covered_elements
            for option in covered_element.options
            for share in option.loan_shares])

        # Use the loan creation date to ensure consistent ordering
        return [x.id for x in sorted(list(loans), key=lambda x: x.create_date)]

    def calculate_premium_aggregates(self, start=None, end=None):
        cursor = Transaction().cursor
        pool = Pool()
        Premium= pool.get('contract.premium')
        invoice = pool.get('account.invoice').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        invoice_contract = pool.get('contract.invoice').__table__()
        premium = Premium.__table__()

        if start:
            date_clause = invoice_line.contract_insurance_start >= start
        else:
            date_clause = None
        if end:
            if date_clause:
                date_clause &= (invoice_line.contract_insurance_start <= end)

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
                *premium_parents, where=date_clause, group_by=premium_parents))
        per_contract_entity = {}
        for elem in cursor.dictfetchall():
            parent = None
            for x in premium_fields:
                if not elem[x]:
                    continue
                parent = premium_parents_models[x](elem[x])
                break
            if parent:
                per_contract_entity[parent] = elem['sum']

        cursor.execute(*query_table.select(premium.rated_entity,
                Sum(invoice_line.unit_price), where=date_clause,
                group_by=premium.rated_entity))
        per_offered_entity = {}
        for elem in cursor.dictfetchall():
            parent = utils.convert_ref_to_obj(elem['rated_entity'])
            per_offered_entity[parent] = elem['sum']

        def result_parser(kind, value=None, model_name=''):
            # kind must be one of 'offered' or 'contract'
            if kind not in ('offered', 'contract'):
                raise KeyError('First parameter must be one of offered /'
                    'contract')
            values = {}
            if kind == 'offered':
                values = per_offered_entity
            elif kind == 'contract':
                values = per_contract_entity
            if value:
                return values.get(value, None)
            if model_name:
                return sum([v for k, v in values.iteritems()
                        if k.__name__ == model_name])
            return values

        return result_parser


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
        return rule.calculate_average_premium_for_contract(self, contract)


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

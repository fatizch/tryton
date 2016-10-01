# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast, Literal
from sql.functions import Substring, Position
from sql.aggregate import Sum
from sql.operators import Concat

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.modules.coog_core import model, fields

__all__ = [
    'SelectDate',
    'CollectionToCashValue',
    'CashValueUpdate',
    'CashSurrenderParameters',
    'CashSurrenderWizard',
    ]


class SelectDate(model.CoogView):
    'Select Date in Collection to Cash Value wizard'

    __name__ = 'contract.wizard.collection_to_cash_value.select_date'

    to_date = fields.Date('To Date', required=True)


class CollectionToCashValue(Wizard):
    'Collection to cash value wizard'

    __name__ = 'contract.wizard.collection_to_cash_value'

    start_state = 'select_date'
    select_date = StateView(
        'contract.wizard.collection_to_cash_value.select_date',
        'contract_cash_value.select_date_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'convert_to_cash_values', 'tryton-go-next')])
    convert_to_cash_values = StateTransition()

    def default_select_date(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        return {
            'to_date': Date.today(),
            }

    # Currently, there is no proper link between the collection and the offered
    # coverage. So we cannot find what has been paid on specific families to
    # create the cash value collections
    def _transition_convert_to_cash_values(self):
        # We look for payment lines on account lines which are paying coverages
        # with the 'cash_value' family tag for which there is not a cash value
        # collection yet
        pool = Pool()
        Collection = pool.get('collection')
        OptionDescription = Pool().get('offered.option.description')
        CashValueCollection = pool.get('contract.cash_value.collection')
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Payment = pool.get('account.payment')
        collection_table = Collection.__table__()
        move_table = Move.__table__()
        cash_value_table = CashValueCollection.__table__()
        line_table = Line.__table__()
        payment_table = Payment.__table__()

        cursor = Transaction().connection.cursor()

        to_date = self.select_date.to_date
        # Accounts to look for
        accounts = [x.account_for_billing.id for x in OptionDescription.search(
                [('family', '=', 'cash_value')])]

        query_table = move_table.join(line_table,
            condition=(
                (line_table.move == move_table.id)
                & (line_table.account.in_(accounts))
                & (line_table.credit != 0))
            ).join(collection_table, condition=(
                    (collection_table.assignment_move == move_table.id)
                    & (collection_table.create_date <=
                        SelectDate.to_date.sql_format(to_date)))
            ).join(cash_value_table, type_='LEFT',
            condition=(
                (cash_value_table.id == None)
                & (cash_value_table.collection == collection_table.id))
            ).join(payment_table, condition=(
                    (payment_table.line == line_table.id)))

        cursor.execute(*query_table.select(Cast(Substring(move_table.origin,
                        Position(',', move_table.origin) + Literal(1)),
                    Move.id.sql_type().base), payment_table.date,
            Sum(payment_table.amount),
            group_by=[
                Cast(Substring(move_table.origin,
                        Position(',', move_table.origin) + Literal(1)),
                    Move.id.sql_type().base),
                payment_table.date]))

        return 'end'

    # Temporary solution : look for cash value contracts with unassigned
    # collections
    def transition_convert_to_cash_values(self):
        pool = Pool()
        Collection = pool.get('collection')
        Configuration = pool.get('account.configuration')
        ProductCoverageRelation = Pool().get(
            'offered.product-option.description')
        CashValueCollection = pool.get('contract.cash_value.collection')
        Move = pool.get('account.move')
        Contract = pool.get('contract')
        OptionDescription = pool.get('offered.option.description')
        Line = pool.get('account.move.line')
        collection_table = Collection.__table__()
        move_table = Move.__table__()
        cash_value_table = CashValueCollection.__table__()
        contract_table = Contract.__table__()

        cursor = Transaction().connection.cursor()
        to_date = self.select_date.to_date

        # Products to look for
        products = list(set([x.product.id
                    for x in ProductCoverageRelation.search([
                            ('coverage.family', '=', 'cash_value')])]))

        # Accounts to look for
        coverage_accounts = dict([(x.account_for_billing.id, x)
                for x in OptionDescription.search([
                        ('family', '=', 'cash_value')])])

        query_table = move_table.join(contract_table, condition=(
                (move_table.origin == Concat('contract,',
                        Cast(contract_table.id, 'VARCHAR')))
                & (contract_table.offered.in_(products))
                & (move_table.post_date <=
                    SelectDate.to_date.sql_format(to_date)))
            ).join(collection_table, condition=(
                    collection_table.assignment_move == move_table.id)
            ).join(cash_value_table, type_='LEFT',
            condition=(cash_value_table.collection == collection_table.id))

        cursor.execute(*query_table.select(contract_table.id,
                collection_table.id, move_table.post_date, where=(
                    cash_value_table.id == None)))

        contracts, collections, dates = zip(*cursor.fetchall())
        contracts = Contract.browse(contracts)
        collections = Collection.browse(collections)
        cashing_moves = []
        for contract, collection, date in zip(contracts, collections, dates):
            target_account, expected_amount = reduce(
                lambda x, y: (x[0] if x[0] else y[0], x[1] + y[1]),
                map(lambda x: (x.account, x.credit), Line.search([
                            ('move.origin', '=', 'contract,%s' %
                                contract.id),
                            ('account', 'in', coverage_accounts.keys()),
                            ('move.post_date', '<=', date)])))
            remaining_amount = expected_amount - sum(map(lambda x: x.amount,
                    CashValueCollection.search([('contract', '=', contract)])))
            if remaining_amount <= 0:
                continue
            cashing_move = Move()
            cashing_move.lines = []
            cash_value = CashValueCollection()
            cash_value.contract = contract
            cash_value.collection = collection
            cash_value.amount = min(remaining_amount, collection.amount)
            cash_value.reception_date = date
            cash_value.last_update = date
            cash_value.updated_amount = cash_value.amount
            cash_value.kind = 'payment'
            cash_value.save()
            cashing_line = Line()
            cashing_line.account = target_account
            cashing_line.debit = cash_value.amount
            cashing_line.party = contract.subscriber
            cashing_line.second_origin = cash_value
            cashing_move.lines.append(cashing_line)
            cashing_line = Line()
            # cashing_line.account = good_coverage.get_result('saving_account',
            #     {'appliable_conditions_date': date})[0]
            cashing_line.credit = cash_value.amount
            cashing_line.party = contract.subscriber
            cashing_line.second_origin = cash_value
            cashing_move.lines.append(cashing_line)
            cashing_move.date = date
            Period = Pool().get('account.period')
            cashing_move.period = Period.find(Transaction().context.get(
                    'company'), date=date, exception=False)
            cashing_move.journal = Configuration(1).cash_value_journal
            cashing_move.save()
            cashing_moves.append(cashing_move)
        Move.post(cashing_moves)
        return 'end'


class CashValueUpdate(Wizard):
    'Wizard to update cash_value_collection'

    __name__ = 'contract.wizard.cash_value_update'

    start_state = 'select_date'
    select_date = StateView(
        'contract.wizard.collection_to_cash_value.select_date',
        'contract_cash_value.select_date_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'update_cash_values', 'tryton-go-next')])
    update_cash_values = StateTransition()

    def default_select_date(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        return {
            'to_date': Date.today(),
            }

    def transition_update_cash_values(self):
        if Transaction().context.get('active_model') != 'contract':
            return 'end'
        if not Transaction().context.get('active_id'):
            return 'end'
        pool = Pool()
        Contract = pool.get('contract')
        CashValueCollection = pool.get('contract.cash_value.collection')
        contract = Contract(Transaction().context.get('active_id'))
        CashValueCollection.update_values(contract.cash_value_collections,
            self.select_date.to_date)
        return 'end'


class CashSurrenderParameters(model.CoogView):
    'Cash Surrender Parameters'

    __name__ = 'contract.wizard.cash_surrender.parameters'

    contract = fields.Many2One('contract', 'Contract', required=True)
    surrender_date = fields.Date('Surrender Date', required=True)
    surrender_amount = fields.Numeric('Surrender Amount')

    @fields.depends('contract', 'surrender_date')
    def on_change_contract(self):
        if not (hasattr(self, 'surrender_date') and self.surrender_date):
            return
        if not (hasattr(self, 'contract') and self.contract):
            return
        pool = Pool()
        CashValueCollection = pool.get('contract.cash_value.collection')
        total_amount = CashValueCollection.update_values(
            self.contract.cash_value_collections,
            self.surrender_date, True, False)
        self.surrender_amount = total_amount

    @fields.depends('contract', 'surrender_date')
    def on_change_surrender_date(self):
        self.on_change_contract()


class CashSurrenderWizard(Wizard):
    'Wizard to trigger a cash surrender'

    __name__ = 'contract.wizard.cash_surrender'

    start_state = 'parameters'
    parameters = StateView('contract.wizard.cash_surrender.parameters',
        'contract_cash_value.parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Surrend', 'surrend', 'tryton-go-next')])
    surrend = StateTransition()

    def default_parameters(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        result = {'surrender_date': Date.today()}
        if (Transaction().context.get('active_model') == 'contract'
                and Transaction().context.get('active_id')):
            result['contract'] = Transaction().context.get('active_id')
            tmp = CashSurrenderParameters()
            tmp.contract = pool.get('contract')(result['contract'])
            tmp.surrender_date = result['surrender_date']
            tmp.on_change_contract()
            result['surrender_amount'] = tmp.surrender_amount
        return result

    def transition_surrend(self):
        pool = Pool()
        CashValueCollection = pool.get('contract.cash_value.collection')
        CashValueCollection.update_values(
            self.parameters.contract.cash_value_collections,
            self.parameters.surrender_date, True)
        self.parameters.contract.status = 'terminated'
        self.parameters.contract.end_date = self.parameters.surrender_date
        self.parameters.contract.save()
        return 'end'

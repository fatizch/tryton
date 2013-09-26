import copy
from decimal import Decimal

from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import StateTransition, StateView, Button, StateAction
from trytond.backend import TableHandler

from trytond.modules.coop_utils import model, fields, utils, coop_date, \
    coop_string

__all__ = [
    'RateLine',
    'RateNote',
    'RateNoteLine',
    'RateNoteParameters',
    'RateNoteParameterClientRelation',
    'RateNoteParameterProductRelation',
    'RateNoteParameterContractRelation',
    'RateNoteParameterGroupPartyRelation',
    'RateNotesDisplayer',
    'RateNoteProcess',
    'RateNoteSelection',
    'RateNoteMoveDisplayer',
    'RateNoteReception',
    'ContractForBilling',
    'Move',
    'MoveLine',
    'CollectionWizard',
    ]


class RateLine(model.CoopSQL, model.CoopView):
    'Rate Line'

    __name__ = 'billing.rate_line'

    manual_billing = fields.Function(
        fields.Boolean('Manual Billing',
            on_change=['manual_billing', 'childs'],
            states={'invisible': True}),
        'get_manual_billing')
    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE',
        states={'invisible': ~~Eval('parent')})
    covered_element = fields.Many2One('ins_contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    option = fields.Many2One('contract.subscribed_option', 'Option',
        ondelete='CASCADE')
    option_ = fields.Function(
        fields.Many2One('contract.subscribed_option', 'Option'),
        'get_option_id')
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        ondelete='RESTRICT', states={'invisible': ~Eval('tranche')})
    fare_class = fields.Many2One('collective.fare_class', 'Fare Class',
        states={'invisible': ~Eval('fare_class_group')})
    index = fields.Many2One('table.table_def', 'Index',
        states={'invisible': ~Eval('index')}, ondelete='RESTRICT')
    indexed_value = fields.Function(
        fields.Numeric('Indexed Value',
            on_change_with=['rate', 'index', 'start_date_']),
        'on_change_with_indexed_value')
    parent = fields.Many2One('billing.rate_line', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('billing.rate_line', 'parent', 'Childs',
        states={'invisible': ~~Eval('tranche')})
    start_date = fields.Date('Start Date')
    start_date_ = fields.Function(
        fields.Date('Start Date'),
        'get_start_date')
    end_date = fields.Date('End Date')
    rate = fields.Numeric('Rate', digits=(16, 4),
        states={'readonly': ~Eval('manual_billing')})

    def add_child(self):
        if utils.is_none(self, 'childs'):
            self.childs = []
        child_line = self.__class__()
        self.childs.append(child_line)
        return child_line

    def add_sub_rate_line(self, rate, tranche=None, fare_class=None,
            index=None):
        child_line = self.add_child()
        child_line.tranche = tranche
        child_line.fare_class = fare_class
        child_line.index = index
        child_line.rate = rate
        return child_line

    def add_option_rate_line(self, option):
        child_line = self.add_child()
        child_line.option = option
        return child_line

    def get_rec_name(self, name):
        if self.covered_element:
            return '%s (%s)' % (self.covered_element.rec_name,
                coop_string.date_as_string(self.start_date))
        elif self.option:
            return self.option.rec_name
        elif self.tranche:
            return self.tranche.rec_name
        elif self.fare_class:
            return self.fare_class.rec_name
        elif self.index:
            return self.index.rec_name

    def create_rate_note_line(self, rate_note_line_model=None):
        if not rate_note_line_model:
            RateNoteLine = Pool().get('billing.rate_note_line')
        else:
            RateNoteLine = rate_note_line_model
        res = RateNoteLine()
        res.rate_line = self
        if not hasattr(res, 'childs'):
            res.childs = []
        for child in self.childs:
            res.childs.append(child.create_rate_note_line(RateNoteLine))
        return res

    def _expand_tree(self, name):
        return True

    def get_manual_billing(self, name):
        if self.contract:
            return self.contract.manual_billing
        elif self.parent:
            return self.parent.manual_billing
        return False

    def on_change_manual_billing(self, value=None):
        if value is None:
            value = self.manual_billing
        if not self.childs:
            return {}
        child_dicts = []
        for c in self.childs:
            child_dict = {'id': c.id, 'manual_billing': value}
            sub_child_dict = c.on_change_manual_billing(value)
            if 'childs' in sub_child_dict:
                child_dict['childs'] = sub_child_dict['childs']
            child_dicts.append(child_dict)
        if child_dicts:
            return {'childs': {'update': child_dicts}}
        else:
            return {}

    def get_option_id(self, name):
        if self.option:
            return self.option.id
        elif self.parent:
            return self.parent.option_.id

    def on_change_with_indexed_value(self, name=None):
        if not self.index:
            return
        Cell = Pool().get('table.table_cell')
        cell = Cell.get_cell(self.index, (self.start_date_))
        value = cell.get_value_with_type() if cell else None
        if value:
            return value * self.rate

    def get_start_date(self, name):
        if self.start_date:
            return self.start_date
        elif self.parent:
            return self.parent.start_date_


class RateNote(model.CoopSQL, model.CoopView):
    'Rate Note'

    __name__ = 'billing.rate_note'

    name = fields.Char('Number', states={'readonly': True})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    status = fields.Selection([
            ('draft', 'Draft'),
            ('ready_to_be_sent', 'Ready to be sent'),
            ('sent', 'Sent'),
            ('completed_by_client', 'Completed by Client'),
            ('validated', 'Validated'),
            ], 'Status', sort=False)
    lines = fields.One2Many('billing.rate_note_line', 'rate_note', 'Lines')
    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE')
    client = fields.Function(
        fields.Many2One('party.party', 'Client'),
        'get_client_id', searcher='search_client')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    move = fields.Many2One('account.move', 'Move',
        states={'invisible': ~Eval('move')})
    amount_paid = fields.Function(fields.Numeric('Amount Paid'),
        'get_amount_paid')
    amount_expected = fields.Function(fields.Numeric('Amount Expected'),
        'get_amount_expected')

    @staticmethod
    def default_status():
        return 'draft'

    def init_data(self, contract, start, end):
        self.start_date = start
        self.end_date = end
        self.status = self.default_status()
        self.contract = contract

    def calculate(self):
        RateNoteLine = Pool().get('billing.rate_note_line')
        if self.status != 'draft':
            return
        if not hasattr(self, 'lines'):
            self.lines = []
        elif self.lines:
            RateNoteLine.delete(self.lines)
            self.lines = list(self.lines)
        for (start_date, end_date), rate_line in self.contract.get_rates(
                self.start_date, self.end_date):
            rate_note_line = rate_line.create_rate_note_line(RateNoteLine)
            rate_note_line.start_date = start_date
            rate_note_line.end_date = end_date
            self.lines.append(rate_note_line)

    def get_client_id(self, name):
        return self.contract.subscriber.id if self.contract else None

    @classmethod
    def search_client(cls, name, clause):
        return [('contract.subscriber',) + tuple(clause[1:])]

    def get_rec_name(self, name):
        return '%s - %s' % (self.name, self.client.rec_name)

    def get_currency(self):
        return self.contract.currency if self.contract else None

    def get_amount_paid(self, name):
        if not self.move:
            return None
        res = sum(map(
                lambda x: x.debit - x.credit - x.payment_amount if
                x.payment_amount else 0,
                filter(lambda x: x.account.kind == 'receivable',
                    self.move.lines)))
        return res

    def get_amount_expected(self, name):
        if not self.move:
            return None
        res = sum(map(
                lambda x: x.debit - x.credit,
                filter(lambda x: x.account.kind == 'receivable',
                    self.move.lines)))
        return res


class RateNoteLine(model.CoopSQL, model.CoopView):
    'Rate Note Line'

    __name__ = 'billing.rate_note_line'

    rate_note = fields.Many2One('billing.rate_note', 'Rate Note',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    base = fields.Numeric('Base', on_change=['base', 'rate', 'indexed_rate'],
        states={'readonly': ~Eval('rate')})
    rate_line = fields.Many2One('billing.rate_line', 'Rate Line')
    amount = fields.Numeric('Amount')
    sum_amount = fields.Function(
        fields.Numeric('Amount',
            on_change_with=['rate', 'childs', 'base', 'indexed_rate'],
            on_change=['amount', 'sum_amount', 'childs'], states={'readonly':
                ~~Eval('childs')},),
        'get_sum_amount', 'setter_void')
    client_amount = fields.Numeric('Client Amount', on_change_with=['base',
            'rate', 'indexed_rate'])
    client_sum_amount = fields.Function(
        fields.Numeric('Client Amount', on_change_with=['rate', 'childs',
                'base', 'indexed_rate'],
                on_change=['client_amount', 'client_sum_amount',
                'childs'], states={'readonly': ~~Eval('childs')},),
        'get_client_sum_amount', 'setter_void')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')
    parent = fields.Many2One('billing.rate_note_line', 'Parent',
        ondelete='CASCADE')
    childs = fields.One2Many('billing.rate_note_line', 'parent', 'Childs')
    rate = fields.Function(fields.Numeric('Rate', digits=(16, 4)), 'get_rate')
    indexed_rate = fields.Function(
        fields.Numeric('Indexed Rate', on_change_with=['rate']),
        'on_change_with_indexed_rate')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        # Migration from X.X: rename quantity to base
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('quantity', 'base')

        super(RateNoteLine, cls).__register__(module_name)

    def get_rec_name(self, name):
        return (self.rate_line.rec_name if self.rate_line
            else super(RateNoteLine, self).get_rec_name(name))

    def get_rate(self, name):
        return (self.rate_line.rate if self.rate_line and self.rate_line.rate
            else None)

    def get_coeff(self):
        if self.indexed_rate:
            return self.indexed_rate
        elif self.rate:
            return self.rate

    def on_change_base(self):
        if hasattr(self, 'rate') and hasattr(self, 'base'):
            coeff = self.get_coeff()
            amount = coeff * self.base if coeff and self.base else None
            return {'amount': amount, 'sum_amount': amount,
                'client_amount': amount}
        return {}

    def get_currency(self):
        if self.parent:
            return self.parent.currency
        elif self.rate_note:
            return self.rate_note.currency

    def on_change_with_sum_amount(self):
        if (hasattr(self, 'childs') and self.childs):
            return sum(map(lambda x: x.sum_amount or 0, self.childs)) or None
        if not (hasattr(self, 'base') and self.base):
            return None
        if not (hasattr(self, 'rate') and self.rate):
            return None
        return self.on_change_base()['sum_amount']

    def on_change_sum_amount(self):
        if (hasattr(self, 'childs') and self.childs):
            return {}
        return {'amount': self.sum_amount}

    def on_change_with_client_amount(self):
        return self.on_change_base()['client_amount']

    def get_sum_amount(self, name):
        if (hasattr(self, 'childs') and self.childs):
            return sum(map(lambda x: x.sum_amount or 0, self.childs)) or None
        if not (hasattr(self, 'amount') and self.amount):
            return None
        return self.amount

    def on_change_with_client_sum_amount(self, name=None):
        if (hasattr(self, 'childs') and self.childs):
            return sum(map(
                    lambda x: x.client_sum_amount or 0, self.childs)) or None
        if not (hasattr(self, 'base') and self.base):
            return None
        if not (hasattr(self, 'rate') and self.rate):
            return None
        return self.on_change_base()['client_amount']

    def on_change_client_sum_amount(self):
        if (hasattr(self, 'childs') and self.childs):
            return {}
        return {'client_amount': self.client_sum_amount}

    def get_client_sum_amount(self, name):
        if (hasattr(self, 'childs') and self.childs):
            return sum(map(
                    lambda x: x.client_sum_amount or 0, self.childs)) or None
        if not (hasattr(self, 'client_amount') and self.client_amount):
            return None
        return self.client_amount

    def _expand_tree(self, name):
        return True

    def get_contract(self):
        if not self.rate_line or not self.rate_line.contract:
            if self.parent:
                return self.parent.get_contract()
            return None
        return self.rate_line.contract

    def calculate_bill_line(self, work_set):
        if not self.amount or not self.client_amount or self.childs:
            for sub_line in self.childs:
                sub_line.calculate_bill_line(work_set)
            return
        bill_line = work_set['lines'][(self.rate_line.covered_element,
                self.rate_line.option_.offered.account_for_billing)]
        bill_line.second_origin = self.rate_line.option_.offered
        bill_line.credit += work_set['currency'].round(self.amount)
        work_set['_remaining'] += work_set['currency'].round(
            self.amount) - work_set['currency'].round(self.client_amount)
        bill_line.account = self.rate_line.option_.offered.account_for_billing
        bill_line.party = self.get_contract().subscriber
        work_set['total_amount'] += work_set['currency'].round(self.amount)

    def on_change_with_indexed_rate(self, name=None):
        if self.rate_line and self.rate_line.indexed_value:
            return self.rate_line.indexed_value


class RateNoteParameters(model.CoopView):
    'Rate Note Parameters'

    __name__ = 'billing.rate_note_process_parameters'

    until_date = fields.Date('Until Date', required=True)
    products = fields.Many2Many('billing.rate_note_process_parameter-product',
        'parameters_view', 'product', 'Products',
        on_change=['products', 'contracts', 'group_clients', 'clients',
            'until_date'],
        domain=[('is_group', '=', True)])
    contracts = fields.Many2Many(
        'billing.rate_note_process_parameter-contract',
        'parameters_view', 'contract', 'Contracts',
        on_change=['products', 'contracts', 'group_clients', 'clients',
            'until_date'],
        domain=[
            ('is_group', '=', True),
            ('status', '=', 'active'),
            ['OR', [('next_assessment_date', '=', None)],
                [('next_assessment_date', '<=', Eval('until_date'))]]
            ], depends=['until_date'])
    group_clients = fields.Many2Many(
        'billing.rate_note_process_parameter-group_client',
        'parameters_view', 'group', 'Group Clients',
        on_change=['products', 'contracts', 'group_clients', 'clients',
            'until_date'])
    clients = fields.Many2Many('billing.rate_note_process_parameter-client',
        'parameters_view', 'client', 'Clients',
        on_change=['products', 'contracts', 'group_clients', 'clients',
            'until_date'])

    def _on_change(self, name):
        Contract = Pool().get('contract.contract')
        res = {}
        clients = self.clients
        contracts = self.contracts
        domain = [
            ('status', '=', 'active'),
            ['OR', [('next_assessment_date', '=', None)],
                [('next_assessment_date', '<=', self.until_date)]],
            ]
        if self.products:
            domain.append(('offered', 'in', [x.id for x in self.products]))
        for group in self.group_clients:
            clients.extend([x for x in group.parties])
        clients.extend([x.subscriber for x in contracts])
        if clients:
            domain.append(('subscriber', 'in', [x.id for x in clients]))
        contracts.extend(Contract.search(domain))

        if clients and name != 'clients':
            res['clients'] = [x.id for x in clients]
        if contracts and name != 'contracts':
            res['contracts'] = [x.id for x in contracts]
        return res

    def on_change_products(self):
        return self._on_change('products')

    def on_change_contracts(self):
        return self._on_change('contracts')

    def on_change_group_clients(self):
        return self._on_change('group_clients')

    def on_change_clients(self):
        return self._on_change('clients')


class RateNoteParameterClientRelation(model.CoopView):
    'Rate Note Parameter Client Relation'

    __name__ = 'billing.rate_note_process_parameter-client'

    parameters_view = fields.Many2One('billing.rate_note_process_parameters',
        'Parameter View')
    client = fields.Many2One('party.party', 'Client')


class RateNoteParameterProductRelation(model.CoopView):
    'Rate Note Parameter Product Relation'

    __name__ = 'billing.rate_note_process_parameter-product'

    parameters_view = fields.Many2One('billing.rate_note_process_parameters',
        'Parameter View')
    product = fields.Many2One('offered.product', 'Product')


class RateNoteParameterContractRelation(model.CoopView):
    'Rate Note Parameter Contract Relation'

    __name__ = 'billing.rate_note_process_parameter-contract'

    parameters_view = fields.Many2One('billing.rate_note_process_parameters',
        'Parameter View')
    contract = fields.Many2One('contract.contract', 'Contract')


class RateNoteParameterGroupPartyRelation(model.CoopView):
    'Rate Note Parameter Group Party Relation'

    __name__ = 'billing.rate_note_process_parameter-group_client'

    parameters_view = fields.Many2One('billing.rate_note_process_parameters',
        'Parameter View')
    group = fields.Many2One('party.group', 'Group Party')


class RateNotesDisplayer(model.CoopView):
    'Rate Notes'

    __name__ = 'billing.rate_notes_displayer'

    rate_notes = fields.One2Many('billing.rate_note', None, 'Rate Notes')


class RateNoteProcess(model.CoopWizard):
    'Rate Note Process'

    __name__ = 'billing.rate_note_process'

    start_state = 'parameters'
    parameters = StateView('billing.rate_note_process_parameters',
        'life_billing_collective_fr.rate_note_process_parameters_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'rate_notes', 'tryton-go-next', default=True),
            ])
    rate_notes = StateView('billing.rate_notes_displayer',
        'life_billing_collective_fr.rate_notes_displayer_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'validate_rate_notes', 'tryton-go-next',
                default=True),
            ])
    validate_rate_notes = StateTransition()

    def default_parameters(self, values):
        Contract = Pool().get('contract.contract')
        contract = None
        if Transaction().context.get('active_model') == 'contract.contract':
            contract = Contract(Transaction().context.get('active_id'))
            if (not contract or not contract.offered.is_group
                    or contract.status != 'active'):
                contract = None
        return {
            'until_date': coop_date.get_end_of_month(utils.today()),
            'contracts': [contract.id] if contract else None,
            'products': [contract.offered.id] if contract else None,
            'clients': [contract.subscriber.id] if contract else None,
            }

    def default_rate_notes(self, values):
        res = {'rate_notes': []}
        for contract in self.parameters.contracts:
            rate_notes = contract.calculate_rate_notes(
                self.parameters.until_date)
            contract.save()
            res['rate_notes'].extend([x.id for x in rate_notes])
        return res

    def transition_validate_rate_notes(self):
        for rate_note in self.rate_notes.rate_notes:
            sequence = rate_note.contract.company.rate_note_sequence
            if sequence:
                rate_note.name = sequence.get_id(sequence.id)
            rate_note.status = 'sent'
            rate_note.save()
        return 'end'


class RateNoteSelection(model.CoopView):
    'Rate Note Selection'

    __name__ = 'billing.rate_note_selection'

    selected_note = fields.Many2One('billing.rate_note', 'Selected Note',
        domain=[('status', '=', 'completed_by_blient')], states={
            'required': True})


class RateNoteMoveDisplayer(model.CoopView):
    'Rate Note Move Displayer'

    __name__ = 'billing.rate_note_move_displayer'

    move = fields.One2Many('account.move', None, 'Move',
        states={'readonly': True})


class RateNoteReception(model.CoopWizard):
    'Rate Note Reception Wizard'

    __name__ = 'billing.rate_note_reception'

    start_state = 'calculate_start'
    calculate_start = StateTransition()
    select_note = StateView('billing.rate_note_selection',
        'life_billing_collective_fr.rate_note_selection_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'preview_bill', 'tryton-ok')])
    preview_bill = StateView('billing.rate_note_move_displayer',
        'life_billing_collective_fr.rate_note_move_displayer_form', [
            Button('Cancel', 'clean_up', 'tryton-cancel'),
            Button('Validate', 'validate', 'tryton-ok')])
    clean_up = StateTransition()
    validate = StateTransition()
    start_collection = StateAction('collection.act_collection_wizard')

    @classmethod
    def __setup__(cls):
        super(RateNoteReception, cls).__setup__()
        cls._error_messages.update({
            'bad_status': 'Selected Rate Note is not in a valid status to '
                'start reception process',
        })

    def transition_calculate_start(self):
        if (Transaction().context.get('active_model') == 'billing.rate_note'
                and Transaction().context.get('active_id')):
            self.select_note.selected_note = Transaction().context.get(
                'active_id')
            if self.select_note.selected_note.status != 'completed_by_client':
                self.raise_user_error('bad_status')
            return 'preview_bill'
        return 'select_note'

    def default_preview_bill(self, name):
        base_note = self.select_note.selected_note
        with Transaction().set_context(rate_note=base_note):
            good_period = base_note.contract.get_billing_period_at_date(
                base_note.start_date)
            if not good_period:
                good_move = base_note.contract.bill().id
            else:
                good_move = base_note.contract.bill(good_period).id
        return {'move': [good_move]}

    def transition_validate(self):
        move = self.preview_bill.move[0]
        if (hasattr(move, 'id') and move.id):
            Move = Pool().get('account.move')
            if move.lines:
                Move.post([move])
                self.select_note.selected_note.move = move
            else:
                Move.delete([move])
        self.select_note.selected_note.status = 'validated'
        self.select_note.selected_note.save()
        return 'start_collection'

    def transition_clean_up(self):
        if (hasattr(self.preview_bill, 'id') and self.preview_bill.id):
            Move = Pool().get('account.move')
            Move.delete([self.preview_bill])
        return 'end'

    def do_start_collection(self, action):
        return action, {
            'model': 'billing.rate_note',
            'id': self.select_note.selected_note.id,
            'ids': [self.select_note.selected_note.id],
            }


class ContractForBilling():
    'Contract'

    __metaclass__ = PoolMeta
    __name__ = 'contract.contract'

    def create_price_list(self, start_date, end_date):
        if not 'rate_note' in Transaction().context:
            return super(ContractForBilling, self).create_price_list(
                start_date, end_date)
        return []

    def calculate_base_lines(self, work_set):
        if not 'rate_note' in Transaction().context:
            return super(ContractForBilling, self).calculate_base_lines(
                work_set)
        rate_note = Transaction().context.get('rate_note')
        work_set['_remaining'] = Decimal(0)
        for rate_line in rate_note.lines:
            rate_line.calculate_bill_line(work_set)
        if not work_set['_remaining']:
            return

        suspense_line = work_set['lines'][(None,
            rate_note.contract.subscriber.suspense_account)]
        suspense_line.second_origin = rate_note
        suspense_line.debit = work_set['_remaining']
        suspense_line.account = rate_note.contract.subscriber.suspense_account
        suspense_line.party = rate_note.contract.subscriber
        work_set['total_amount'] -= suspense_line.debit

    def compensate_existing_moves_on_period(self, work_set):
        if not 'rate_note' in Transaction().context:
            return super(
                ContractForBilling, self).compensate_existing_moves_on_period(
                    work_set)
        # No compensation when billing a rate note
        pass


class Move():
    'Move'

    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.coverage_details = copy.copy(cls.coverage_details)
        cls.coverage_details.domain[1].append(
            ('second_origin', 'like', 'billing.rate_note,%'))


class MoveLine():
    'Move Line'

    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    @classmethod
    def _get_second_origin(cls):
        result = super(MoveLine, cls)._get_second_origin()
        result.append('billing.rate_note')
        return result

    def get_second_origin_name(self, name):
        if not (hasattr(self, 'second_origin') and self.second_origin):
            return ''
        if not self.second_origin.__name__ == 'billing.rate_note':
            return super(MoveLine, self).get_second_origin_name(name)
        return 'Rate Note compensation'


class CollectionWizard():
    'Collection Wizard'

    __metaclass__ = PoolMeta
    __name__ = 'collection.collection_wizard'

    def default_input_collection_parameters(self, name):
        res = super(
            CollectionWizard, self).default_input_collection_parameters(name)
        the_model = Transaction().context.get('active_model', None)
        if not the_model or the_model != 'billing.rate_note':
            return res
        rate_note = Pool().get(the_model)(
            Transaction().context.get('active_id'))
        res['contract'] = rate_note.contract.id
        res['party'] = rate_note.contract.subscriber.id
        res['amount'] = rate_note.amount_expected
        res['kind'] = 'check'
        return res

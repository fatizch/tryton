from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import StateTransition, StateView, Button
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
    ]


class RateLine(model.CoopSQL, model.CoopView):
    'Rate Line'

    __name__ = 'billing.rate_line'

    manual_billing = fields.Function(
        fields.Boolean('Manual Biiling',
            on_change=['manual_billing', 'childs']),
        'get_manual_billing')
    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE',
        states={'invisible': ~~Eval('parent')})
    covered_element = fields.Many2One('ins_contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    option = fields.Many2One('contract.subscribed_option', 'Option',
        ondelete='CASCADE')
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        ondelete='RESTRICT', states={'invisible': ~Eval('tranche')})
    fare_class = fields.Many2One('collective.fare_class', 'Fare Class',
        states={'invisible': ~Eval('fare_class_group')})
    index = fields.Many2One('table.table_def', 'Index',
        states={'invisible': ~Eval('index')}, ondelete='RESTRICT')
    parent = fields.Many2One('billing.rate_line', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('billing.rate_line', 'parent', 'Childs',
        states={'invisible': ~~Eval('tranche')})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    rate = fields.Numeric('Rate', digits=(16, 4),
        states={'readonly': ~Eval('manual_billing')})
    reference_value = fields.Function(
        fields.Char('Reference Value'),
        'get_reference_value')

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
            sub_child_dict = c.on_change_manual_billing(value)
            if not 'childs' in sub_child_dict:
                continue
            child_dicts.append({
                        'id': c.id,
                        'manual_billing': value,
                        'childs': sub_child_dict['childs']})
        if child_dicts:
            return {'childs': {'update': child_dicts}}
        else:
            return {}


class RateNote(model.CoopSQL, model.CoopView):
    'Rate Note'

    __name__ = 'billing.rate_note'
    _rec_name = 'client'

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
        return '%s (%s - %s)' % (self.client.rec_name,
            coop_string.date_as_string(self.start_date),
            coop_string.date_as_string(self.end_date))

    def get_currency(self):
        return self.contract.currency if self.contract else None


class RateNoteLine(model.CoopSQL, model.CoopView):
    'Rate Note Line'

    __name__ = 'billing.rate_note_line'

    rate_note = fields.Many2One('billing.rate_note', 'Rate Note',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    base = fields.Numeric('Base', on_change=['base', 'rate'],
        states={'readonly': ~Eval('rate')})
    rate_line = fields.Many2One('billing.rate_line', 'Rate Line')
    amount = fields.Numeric('Amount')
    sum_amount = fields.Function(
        fields.Numeric('Amount', on_change_with=['amount', 'childs', 'base']),
        'on_change_with_sum_amount', 'setter_void')
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

    def on_change_base(self):
        if hasattr(self, 'rate') and hasattr(self, 'base'):
            amount = self.rate * self.base if self.rate and self.base else None
            return {'amount': amount, 'sum_amount': amount}
        return {}

    def get_currency(self):
        if self.parent:
            return self.parent.currency
        elif self.rate_note:
            return self.rate_note.currency

    def on_change_with_sum_amount(self, name=None):
        return (self.amount if self.amount else 0) + sum(
            map(lambda x: x.sum_amount, self.childs))

    def _expand_tree(self, name):
        return True


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
            rate_note.save()
        return 'end'

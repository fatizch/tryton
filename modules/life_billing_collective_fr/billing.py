from trytond.pyson import Eval, Or
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import StateTransition, StateView, Button, StateAction
from trytond.modules.coop_utils import model, fields, utils, coop_date, \
    coop_string
from trytond.modules.coop_currency import ModelCurrency
from trytond.modules.rule_engine import RuleEngineResult
from trytond.modules.insurance_product import business_rule

__all__ = [
    'PremiumRateLine',
    'RateNote',
    'RateNoteLine',
    'BillingPremiumRateFormCreateParam',
    'BillingPremiumRateFormCreateParamClient',
    'BillingPremiumRateFormCreateParamProduct',
    'BillingPremiumRateFormCreateParamContract',
    'BillingPremiumRateFormCreateParamGroupClient',
    'BillingPremiumRateFormCreateShowForms',
    'BillingPremiumRateFormCreate',
    'BillingPremiumRateFormReceiveSelect',
    'BillingPremiumRateFormReceiveCreateMove',
    'BillingPremiumRateFormReceive',
    'PremiumRateRule',
    'PremiumRateRuleLine',
    'FareClass',
    'FareClassGroup',
    'FareClassGroupFareClassRelation',
    ]


class PremiumRateLine(model.CoopSQL, model.CoopView):
    'Premium Rate Line'

    __name__ = 'contract.premium_rate.line'

    manual_billing = fields.Function(
        fields.Boolean('Manual Billing',
            on_change=['manual_billing', 'childs'],
            states={'invisible': True}),
        'get_manual_billing')
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        states={'invisible': ~~Eval('parent')})
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE')
    option_ = fields.Function(
        fields.Many2One('contract.option', 'Option'),
        'get_option_id')
    tranche = fields.Many2One('salary_range', 'Salary Range',
        ondelete='RESTRICT', states={'invisible': ~Eval('tranche')})
    fare_class = fields.Many2One('fare_class', 'Fare Class',
        states={'invisible': ~Eval('fare_class_group')})
    index = fields.Many2One('table', 'Index',
        states={'invisible': ~Eval('index')}, ondelete='RESTRICT')
    index_value = fields.Function(
        fields.Numeric('Index Value'),
        'get_index_value')
    indexed_value = fields.Function(
        fields.Numeric('Indexed Value',
            on_change_with=['rate', 'index', 'start_date_', 'index_value']),
        'on_change_with_indexed_value')
    parent = fields.Many2One('contract.premium_rate.line', 'Parent',
        ondelete='CASCADE')
    childs = fields.One2Many('contract.premium_rate.line', 'parent', 'Childs',
        states={'invisible': ~~Eval('tranche')})
    start_date = fields.Date('Start Date')
    start_date_ = fields.Function(
        fields.Date('Start Date'),
        'get_start_date')
    end_date = fields.Date('End Date')
    rate = fields.Numeric('Rate', digits=(16, 4),
        states={'readonly': Or(~Eval('manual_billing'), ~~Eval('childs'))})

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
            RateNoteLine = Pool().get('billing.premium_rate.form.line')
        else:
            RateNoteLine = rate_note_line_model
        res = RateNoteLine()
        res.rate_line = self
        res.rate = self.rate
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
        return self.index_value * self.rate if self.index_value else None

    def get_index_value(self, name):
        if not self.index:
            return
        Cell = Pool().get('table.cell')
        cell = Cell.get_cell(self.index, (self.start_date_))
        return cell.get_value_with_type() if cell else None

    def get_start_date(self, name):
        if self.start_date:
            return self.start_date
        elif self.parent:
            return self.parent.start_date_


class RateNote(model.CoopSQL, model.CoopView, ModelCurrency):
    'Rate Note'

    __name__ = 'billing.premium_rate.form'

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
    lines = fields.One2Many('billing.premium_rate.form.line', 'rate_note',
        'Lines')
    contract = fields.Many2One('contract', 'Contract',
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
        RateNoteLine = Pool().get('billing.premium_rate.form.line')
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


class RateNoteLine(model.CoopSQL, model.CoopView, ModelCurrency):
    'Rate Note Line'

    __name__ = 'billing.premium_rate.form.line'

    rate_note = fields.Many2One('billing.premium_rate.form', 'Rate Note',
        ondelete='CASCADE')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_contract_id')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    base = fields.Numeric('Base',
        on_change=['base', 'rate', 'indexed_rate', 'amount', 'rate_line',
            'client_amount'],
        states={'readonly': ~~Eval('childs')})
    rate_line = fields.Many2One('contract.premium_rate.line',
        'Premium Rate Line')
    amount = fields.Numeric('Amount',
        on_change=['base', 'rate', 'indexed_rate', 'amount', 'rate_line'],
        states={'readonly': ~~Eval('childs')})
    client_amount = fields.Numeric('Client Amount',
        on_change=['base', 'rate', 'indexed_rate', 'amount', 'rate_line',
            'client_amount'],
        states={'readonly': ~~Eval('childs')})
    parent = fields.Many2One('billing.premium_rate.form.line', 'Parent',
        ondelete='CASCADE')
    childs = fields.One2Many('billing.premium_rate.form.line', 'parent',
        'Childs')
    rate = fields.Numeric('Rate', digits=(16, 4),
        on_change=['base', 'rate', 'indexed_rate', 'amount', 'rate_line',
            'client_amount'], states={'readonly': ~~Eval('childs')})
    indexed_rate = fields.Function(
        fields.Numeric('Indexed Rate'),
        'get_indexed_rate')
    sum_amount = fields.Function(
        fields.Numeric('Sum Amount', on_change_with=['childs', 'amount']),
        'on_change_with_sum_amount')
    client_sum_amount = fields.Function(
        fields.Numeric('Client Sum Amount',
            on_change_with=['childs', 'client_amount']),
        'on_change_with_client_sum_amount')

    def get_rec_name(self, name):
        return (self.rate_line.rec_name if self.rate_line
            else super(RateNoteLine, self).get_rec_name(name))

    def _on_change(self, name):
        res = {}
        if self.indexed_rate:
            coeff = self.rate_line.index_value * self.rate
        else:
            coeff = self.rate
        if name in ['base', 'rate']:
            if name == 'rate' and self.indexed_rate:
                res['indexed_rate'] = coeff
            amount = coeff * self.base if coeff and self.base else None
            res['amount'] = amount
        else:
            amount = self.amount
        if name == 'client_amount':
            res['client_sum_amount'] = self.client_amount
        else:
            res['client_amount'] = amount
            res['sum_amount'] = amount
            res['client_sum_amount'] = amount
        return res

    def on_change_base(self):
        return self._on_change('base')

    def on_change_rate(self):
        return self._on_change('rate')

    def on_change_amount(self):
        return self._on_change('amount')

    def on_change_client_amount(self):
        return self._on_change('client_amount')

    def get_indexed_rate(self, name):
        return (self.rate_line.index_value * self.rate
            if self.rate_line.index_value else None)

    def get_currency(self):
        if self.parent:
            return self.parent.currency
        elif self.rate_note:
            return self.rate_note.currency

    def _expand_tree(self, name):
        return True

    def get_contract_id(self, name):
        if not self.rate_line or not self.rate_line.contract:
            if self.parent:
                return self.parent.contract.id
            return None
        return self.rate_line.contract.id

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
        bill_line.party = self.contract.subscriber
        work_set['total_amount'] += work_set['currency'].round(self.amount)

    def on_change_with_sum_amount(self, name=None):
        if (hasattr(self, 'childs') and self.childs):
            return sum(map(lambda x: x.sum_amount or 0, self.childs)) or None
        if not (hasattr(self, 'amount') and self.amount):
            return None
        return self.amount

    def on_change_with_client_sum_amount(self, name=None):
        if (hasattr(self, 'childs') and self.childs):
            return (sum(map(lambda x: x.client_sum_amount or 0, self.childs))
                or None)
        if not (hasattr(self, 'client_amount') and self.client_amount):
            return None
        return self.client_amount


class BillingPremiumRateFormCreateParam(model.CoopView):
    'Billing Premium Rate Form Create Param'

    __name__ = 'billing.premium_rate.form.create.param'

    until_date = fields.Date('Until Date', required=True)
    products = fields.Many2Many(
        'billing.premium_rate.form.create.param-product', 'parameters_view',
        'product', 'Products', on_change=['products', 'contracts',
        'group_clients', 'clients', 'until_date'],
        domain=[('is_group', '=', True)])
    contracts = fields.Many2Many(
        'billing.premium_rate.form.create.param-contract',
        'parameters_view', 'contract', 'Contracts',
        on_change=['products', 'contracts', 'group_clients', 'clients',
            'until_date'], domain=[
            ('is_group', '=', True),
            ('status', '=', 'active'),
            ['OR', [('next_assessment_date', '=', None)],
                [('next_assessment_date', '<=', Eval('until_date'))]]
            ], depends=['until_date'])
    group_clients = fields.Many2Many(
        'billing.premium_rate.form.create.param-group_client',
        'parameters_view', 'group', 'Group Clients',
        on_change=['products', 'contracts', 'group_clients', 'clients',
            'until_date'])
    clients = fields.Many2Many('billing.premium_rate.form.create.param-client',
        'parameters_view', 'client', 'Clients',
        on_change=['products', 'contracts', 'group_clients', 'clients',
            'until_date'])

    def _on_change(self, name):
        Contract = Pool().get('contract')
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


class BillingPremiumRateFormCreateParamClient(model.CoopView):
    'Billing Premium Rate Form Create Param Client'

    __name__ = 'billing.premium_rate.form.create.param-client'

    parameters_view = fields.Many2One('billing.premium_rate.form.create.param',
        'Parameter View')
    client = fields.Many2One('party.party', 'Client')


class BillingPremiumRateFormCreateParamProduct(model.CoopView):
    'Billing Premium Rate Form Create Param Product'

    __name__ = 'billing.premium_rate.form.create.param-product'

    parameters_view = fields.Many2One('billing.premium_rate.form.create.param',
        'Parameter View')
    product = fields.Many2One('offered.product', 'Product')


class BillingPremiumRateFormCreateParamContract(model.CoopView):
    'Billing Premium Rate Form Create Param Contract'

    __name__ = 'billing.premium_rate.form.create.param-contract'

    parameters_view = fields.Many2One('billing.premium_rate.form.create.param',
        'Parameter View')
    contract = fields.Many2One('contract', 'Contract')


class BillingPremiumRateFormCreateParamGroupClient(model.CoopView):
    'Billing Premium Rate Form Create Param Group Client'

    __name__ = 'billing.premium_rate.form.create.param-group_client'

    parameters_view = fields.Many2One('billing.premium_rate.form.create.param',
        'Parameter View')
    group = fields.Many2One('party.group', 'Group Party')


class BillingPremiumRateFormCreateShowForms(model.CoopView):
    'Billing Premium Rate Form Create Show Forms'

    __name__ = 'billing.premium_rate.form.create.show_forms'

    rate_notes = fields.One2Many('billing.premium_rate.form', None,
        'Rate Notes')


class BillingPremiumRateFormCreate(model.CoopWizard):
    'Billing Premium Rate Form Create'

    __name__ = 'billing.premium_rate.form.create'

    start_state = 'parameters'
    parameters = StateView('billing.premium_rate.form.create.param',
        'life_billing_collective_fr.rate_note_process_parameters_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'rate_notes', 'tryton-go-next', default=True),
            ])
    rate_notes = StateView('billing.premium_rate.form.create.show_forms',
        'life_billing_collective_fr.rate_notes_displayer_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'validate_rate_notes', 'tryton-go-next',
                default=True),
            ])
    validate_rate_notes = StateTransition()

    def default_parameters(self, values):
        Contract = Pool().get('contract')
        contract = None
        if Transaction().context.get('active_model') == 'contract':
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


class BillingPremiumRateFormReceiveSelect(model.CoopView):
    'Billing Premium Rate Form Receive Select'

    __name__ = 'billing.premium_rate.form.receive.select'

    selected_note = fields.Many2One('billing.premium_rate.form',
        'Selected Note', domain=[('status', '=', 'completed_by_blient')],
        states={'required': True})


class BillingPremiumRateFormReceiveCreateMove(model.CoopView):
    'Billing Premium Rate Form Receive Create Move'

    __name__ = 'billing.premium_rate.form.receive.create_move'

    move = fields.One2Many('account.move', None, 'Move',
        states={'readonly': True})


class BillingPremiumRateFormReceive(model.CoopWizard):
    'Billing Premium Rate Form Receive'

    __name__ = 'billing.premium_rate.form.receive'

    start_state = 'calculate_start'
    calculate_start = StateTransition()
    select_note = StateView('billing.premium_rate.form.receive.select',
        'life_billing_collective_fr.rate_note_selection_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'preview_bill', 'tryton-ok')])
    preview_bill = StateView('billing.premium_rate.form.receive.create_move',
        'life_billing_collective_fr.rate_note_move_displayer_form', [
            Button('Cancel', 'clean_up', 'tryton-cancel'),
            Button('Validate', 'validate', 'tryton-ok')])
    clean_up = StateTransition()
    validate = StateTransition()
    start_collection = StateAction('collection.act_collection_wizard')

    @classmethod
    def __setup__(cls):
        super(BillingPremiumRateFormReceive, cls).__setup__()
        cls._error_messages.update({
                'bad_status': 'Selected Rate Note is not in a valid status to '
                'start reception process',
                })

    def transition_calculate_start(self):
        if (Transaction().context.get(
                    'active_model') == 'billing.premium_rate.form'
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
                max(base_note.start_date, base_note.contract.start_date))
            if not good_period:
                good_move = base_note.contract.bill().id
            else:
                good_move = base_note.contract.bill(*good_period).id
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
            'model': 'billing.premium_rate.form',
            'id': self.select_note.selected_note.id,
            'ids': [self.select_note.selected_note.id],
            }


class FareClass(model.CoopSQL, model.CoopView):
    'Fare Class'

    __name__ = 'fare_class'

    code = fields.Char('Code', on_change_with=['code', 'name'], required=True)
    name = fields.Char('Name')

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class FareClassGroup(model.CoopSQL, model.CoopView):
    'Fare Class Group'

    __name__ = 'fare_class.group'

    code = fields.Char('Code', on_change_with=['code', 'name'], required=True)
    name = fields.Char('Name')
    fare_classes = fields.Many2Many('fare_class.group-fare_class',
        'group', 'fare_class', 'Fare Classes')

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class FareClassGroupFareClassRelation(model.CoopSQL):
    'Relation between fare class group and fare class'

    __name__ = 'fare_class.group-fare_class'

    group = fields.Many2One('fare_class.group', 'Group',
        ondelete='CASCADE')
    fare_class = fields.Many2One('fare_class', 'Fare Class',
        ondelete='RESTRICT')


class PremiumRateRule(business_rule.BusinessRuleRoot, model.CoopSQL):
    'Premium Rate Rule'

    __name__ = 'billing.premium.rate.rule'

    rating_kind = fields.Selection(
        [('tranche', 'by Salary Range'), ('fare_class', 'by Fare Class')],
        'Rating Kind', states={'readonly': ~~Eval('sub_rating_rules')})
    sub_rating_rules = fields.One2Many('billing.premium.rate.rule.line',
        'main_rating_rule', 'Premium Rate Rule Lines')
    index = fields.Many2One('table', 'Index',
        domain=[
            ('dimension_kind1', '=', 'range-date'),
            ('dimension_kind2', '=', None),
            ], states={'invisible': Eval('rating_kind') != 'fare_class'},
            ondelete='RESTRICT')

    def give_me_rate(self, args):
        result = []
        errs = []
        for cov_data in args['option'].covered_data:
            #TODO deal with date control, do not rate a future covered data
            cov_data_dict = {'covered_data': cov_data, 'rates': [],
                'date': args['date']}
            result.append(cov_data_dict)
            cov_data_args = args.copy()
            cov_data.init_dict_for_rule_engine(cov_data_args)
            for sub_rule in self.sub_rating_rules:
                if self.rating_kind == 'fare_class':
                    if sub_rule.fare_class_group != cov_data.fare_class_group:
                        continue
                    cov_data_args['fare_class'] = sub_rule.fare_class
                    cov_data_args['fare_class_group'] = \
                        cov_data.fare_class_group
                rule_engine_res = sub_rule.get_result(cov_data_args)
                if rule_engine_res.errors:
                    errs += rule_engine_res.errors
                    continue
                cur_dict = {'rate': rule_engine_res.result}
                if self.rating_kind == 'fare_class':
                    cur_dict['key'] = sub_rule.fare_class
                    cur_dict['index'] = self.index
                    cur_dict['kind'] = 'fare_class'
                elif self.rating_kind == 'tranche':
                    cur_dict['key'] = sub_rule.tranche
                    cur_dict['kind'] = 'tranche'
                cov_data_dict['rates'].append(cur_dict)
        return result, errs

    @staticmethod
    def default_rating_kind():
        return 'fare_class'


class PremiumRateRuleLine(model.CoopView, model.CoopSQL):
    'Premium Rate Rule Line'

    __name__ = 'billing.premium.rate.rule.line'

    main_rating_rule = fields.Many2One('billing.premium.rate.rule',
        'Main Rating Rule', ondelete='CASCADE')
    tranche = fields.Many2One('salary_range', 'Salary Range',
        states={'invisible': Eval('_parent_main_rating_rule', {}).get(
                'rating_kind', '') != 'tranche'}, ondelete='RESTRICT')
    fare_class_group = fields.Many2One('fare_class.group',
        'Fare Class Group',
        states={'invisible': Eval('_parent_main_rating_rule', {}).get(
                    'rating_kind', '') != 'fare_class'}, ondelete='RESTRICT',
        domain=[('fare_classes', '=', Eval('fare_class'))],
        depends=['fare_class'])
    fare_class = fields.Many2One('fare_class', 'Fare Class',
        states={'invisible': Eval('_parent_main_rating_rule', {}).get(
                    'rating_kind', '') != 'fare_class'},
        ondelete='RESTRICT')
    config_kind = fields.Selection(business_rule.CONFIG_KIND, 'Conf. kind',
        required=True)
    simple_rate = fields.Numeric('Rate',
        states={'invisible': ~business_rule.STATE_SIMPLE}, digits=(16, 4))
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='RESTRICT',
        states={'invisible': ~business_rule.STATE_ADVANCED})

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_result(self, args):
        if self.config_kind == 'simple':
            return RuleEngineResult(self.simple_rate)
        elif self.rule:
            return self.rule.execute(args)

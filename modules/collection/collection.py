from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button, StateTransition

from trytond.modules.coop_utils import fields, model


__metaclass__ = PoolMeta
__all__ = [
    'Collection',
    'CollectionCreateParameters',
    'CollectionCreateAssignLines',
    'CollectionCreateAssign',
    'CollectionCreate',
    ]

COLLECTION_KIND = [
    ('cash', 'Cash'),
    ('check', 'Check'),
    ]


class Collection(model.CoopSQL, model.CoopView):
    'Collection'

    __name__ = 'collection'

    amount = fields.Numeric('Amount', states={'readonly': True})
    kind = fields.Selection(COLLECTION_KIND, 'Kind',
        states={'readonly': True})
    assignment_move = fields.Many2One('account.move', 'Assignment Move',
        states={'readonly': True})
    party = fields.Many2One('party.party', 'Party', states={'readonly': True})
    create_user = fields.Function(
        fields.Many2One('res.user', 'Created by', states={'readonly': True}),
        'get_create_user')
    check_number = fields.Char('Check Number', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check',
            })
    check_reception_date = fields.Date('Check Reception Date', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check',
            })

    def get_create_user(self, name):
        return self.create_uid.id


class CollectionCreateParameters(model.CoopView):
    'Collection Create Parameters'

    __name__ = 'collection.create.parameters'

    kind = fields.Selection(COLLECTION_KIND, 'Kind', required=True)
    amount = fields.Numeric('Amount', required=True)
    party = fields.Many2One('party.party', 'Party', required=True)
    check_number = fields.Char('Check Number', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check',
            })
    check_reception_date = fields.Date('Check Reception Date', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check',
            })
    collection = fields.Many2One('collection', 'Collection',
        states={'invisible': True})


class CollectionCreateAssignLines(model.CoopView):
    'Collection Create Assign Lines'

    __name__ = 'collection.create.assign.lines'

    amount = fields.Numeric('Amount', on_change_with=['source_move_line'])
    source_move_line = fields.Many2One('account.move.line', 'Source Move Line',
        states={'invisible': Eval('kind') != 'move_line'}, domain=[
            ('party', '=', Eval('context', {}).get('from_party')),
            ('account.kind', '=', 'receivable'),
            ('move.state', '=', 'posted'),
            ('payment_amount', '>', 0)])
    target_account = fields.Many2One('account.account', 'Target Account',
        required=True, on_change_with=['source_move_line'],
        domain=[('kind', '=', 'receivable'), ('move.state', '=', 'posted')])
    kind = fields.Selection([
            ('move_line', 'From Move Line'),
            ('select_account', 'Select Account')],
        'Kind', on_change=['kind', 'source_move_line', 'target_account'])

    @classmethod
    def __setup__(cls):
        super(CollectionCreateAssignLines, cls).__setup__()
        cls._error_messages.update({
            'amount_too_big': 'Amount (%s) for line is too big. It must'
            'be lower than %s',
        })

    def on_change_with_target_account(self):
        if not (hasattr(self, 'source_move_line') and self.source_move_line):
            return None
        return self.source_move_line.account.id

    def on_change_kind(self):
        if self.kind == 'move_line':
            return {'source_move_line': None, 'target_account': None}
        elif self.kind == 'select_account':
            return {'source_move_line': None}

    def on_change_with_amount(self):
        if not (hasattr(self, 'source_move_line') and self.source_move_line):
            return 0
        return self.source_move_line.payment_amount

    @classmethod
    def default_kind(cls):
        return 'move_line'

    def pre_validate(self):
        # TODO : Check remaining is enough for the line
        return True


class CollectionCreateAssign(model.CoopView):
    'Collection Create Assign'

    __name__ = 'collection.create.assign'

    amount = fields.Numeric('Amount')
    party = fields.Many2One('party.party', 'Party')
    assignments = fields.One2Many('collection.create.assign.lines', None,
        'Assignments',
        context={'from_party': Eval('party'), 'remaining': Eval('remaining')},
        depends=['party'])
    create_suspense_line_with_rest = fields.Boolean(
        'Create Suspense Line from Remaining', states={
            'invisible': ~Eval('remaining')})
    remaining = fields.Numeric('Remaining', on_change_with=['amount',
            'assignments'])

    def on_change_with_remaining(self):
        if not (hasattr(self, 'amount') and self.amount):
            return None
        if not (hasattr(self, 'assignments') and self.assignments):
            return None
        return self.amount - sum(map(
                lambda x: x.amount or 0, self.assignments))


class CollectionCreate(model.CoopWizard):
    'Collection Create'

    __name__ = 'collection.create'

    start_state = 'input_collection_parameters'
    input_collection_parameters = StateView('collection.create.parameters',
        'collection.collection_parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Assign', 'assign', 'tryton-go-next')])
    assign = StateView('collection.create.assign',
        'collection.assign_collection_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'check_amount', 'tryton-ok')])
    check_amount = StateTransition()
    validate = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CollectionCreate, cls).__setup__()
        cls._error_messages.update({
                'bad_ventilation': 'Ventilation is not consistent : %s '
                'declared, %s assigned',
                })

    def default_input_collection_parameters(self, name):
        res = {'kind': 'cash'}
        if Transaction().context.get('active_model') == 'party':
            res['party'] = Transaction().context.get('active_id')
        return res

    def default_assign(self, name):
        return {
            'party': self.input_collection_parameters.party.id,
            'amount': self.input_collection_parameters.amount,
            'remaining': self.input_collection_parameters.amount,
            }

    def transition_check_amount(self):
        if self.assign.create_suspense_line_with_rest:
            return 'validate'
        amount = self.assign.amount
        ventilated_amount = sum(map(lambda x: x.amount,
                self.assign.assignments))
        if amount != ventilated_amount:
            self.raise_user_error('bad_ventilation', (amount,
                    ventilated_amount))
        return 'validate'

    def get_collection_move(self):
        pool = Pool()
        Move = pool.get('account.move')
        AccountConfiguration = pool.get('account.configuration')
        Date = pool.get('ir.date')
        account_configuration = AccountConfiguration(1)
        collection_move = Move()
        collection_move.journal = account_configuration.collection_journal
        collection_move.date = Date.today()
        collection_move.lines = []
        return collection_move

    def transition_validate(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        Collection = pool.get('collection')
        Company = pool.get('company.company')
        Payment = pool.get('account.payment')
        AccountConfiguration = pool.get('account.configuration')
        Date = pool.get('ir.date')
        account_configuration = AccountConfiguration(1)
        PaymentGroup = pool.get('account.payment.group')
        company = Company(Transaction().context.get('company'))
        remaining = self.assign.amount
        payments = []
        collection_move = self.get_collection_move()
        for line in self.assign.assignments:
            new_line = MoveLine()
            new_line.account = line.target_account
            new_line.party = self.assign.party
            new_line.credit = line.amount
            collection_move.lines.append(new_line)
            remaining -= line.amount
            if not line.kind == 'move_line':
                continue
            new_payment = Payment()
            currency = line.source_move_line.second_currency \
                or company.currency
            new_payment.journal = company.get_payment_journal(currency)
            new_payment.kind = 'receivable'
            new_payment.party = self.assign.party
            new_payment.date = Date.today()
            new_payment.amount = line.amount
            new_payment.line = line.source_move_line
            new_payment.state = 'succeeded'
            payments.append(new_payment)
        if remaining:
            suspense_line = MoveLine()
            suspense_line.credit = remaining
            suspense_line.account = self.assign.party.suspense_account
            suspense_line.party = self.assign.party
            collection_move.lines.append(suspense_line)
        collection_line = MoveLine()
        collection_line.party = self.assign.party
        collection_line.debit = self.assign.amount
        collection_line.account = getattr(account_configuration, '%s_account' %
            self.input_collection_parameters.kind)
        collection_move.lines.append(collection_line)
        collection_move.save()
        Move.post([collection_move])
        log = Collection()
        log.party = self.input_collection_parameters.party
        log.amount = self.assign.amount
        log.kind = self.input_collection_parameters.kind
        log.assignment_move = collection_move
        if self.input_collection_parameters.check_number:
            log.check_number = self.input_collection_parameters.check_number
            log.check_reception_date = \
                self.input_collection_parameters.check_reception_date
        log.save()
        if payments:
            payment_group = PaymentGroup()
            payment_group.company = company
            payment_group.journal = company.get_payment_journal(
                company.currency)
            payment_group.kind = 'receivable'
            payment_group.payments = []
            for payment in payments:
                payment.collection = log
                payment_group.payments.append(payment)
            payment_group.payments = payments
            payment_group.save()
        return 'end'

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button, StateTransition

from trytond.modules.coop_utils import fields, model


__all__ = [
    'Company',
    'Configuration',
    'SuspenseParty',
    'Collection',
    'CollectionParameters',
    'Assignment',
    'AssignCollection',
    'CollectionWizard',
    ]


class Company():
    'Company'

    __metaclass__ = PoolMeta
    __name__ = 'company.company'

    cash_account = fields.Many2One('account.account', 'Cash Account',
        required=True)
    check_account = fields.Many2One('account.account', 'Check Account',
        required=True)
    collection_journal = fields.Many2One('account.journal', 'Journal',
        required=True)


class Configuration():
    'Account Configuration'

    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    default_suspense_account = fields.Function(fields.Many2One(
        'account.account', 'Default Suspense Account',
        domain=[
                ('kind', '=', 'other'),
                ('company', '=', Eval('context', {}).get('company')),
                ]),
        'get_account', setter='set_account')


class SuspenseParty():
    'Party'

    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    suspense_account = fields.Property(fields.Many2One('account.account',
            'Suspense Account', domain=[
                ('kind', '=', 'other'),
                ('company', '=', Eval('context', {}).get('company')),
                ],
            states={
                'required': ~~(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))


class Collection(model.CoopSQL, model.CoopView):
    'Collection'

    __name__ = 'collection.collection'

    amount = fields.Numeric('Amount', states={'readonly': True})
    kind = fields.Selection([('cash', 'Cash'), ('check', 'Check')], 'Kind',
        states={'readonly': True})
    assignment_move = fields.Many2One('account.move', 'Assignment Move',
        states={'readonly': True})
    party = fields.Many2One('party.party', 'Party', states={'readonly': True})
    create_user = fields.Function(
        fields.Many2One('res.user', 'Created by', states={'readonly': True}),
        'get_create_user')
    check_number = fields.Char('Check Number', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check'})

    def get_create_user(self, name):
        return self.create_uid.id


class CollectionParameters(model.CoopView):
    'Collection parameters'

    __name__ = 'collection.collection_parameters'

    kind = fields.Selection([('cash', 'Cash'), ('check', 'Check')], 'Kind',
        required=True)
    amount = fields.Numeric('Amount', required=True)
    party = fields.Many2One('party.party', 'Party', required=True)
    check_number = fields.Char('Check Number', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check'})


class Assignment(model.CoopView):
    'Assignment'

    __name__ = 'collection.assignment'

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
        super(Assignment, cls).__setup__()
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


class AssignCollection(model.CoopView):
    'Assign Collection'

    __name__ = 'collection.assign_collection'

    amount = fields.Numeric('Amount', states={'readonly': True})
    party = fields.Many2One('party.party', 'Party')
    assignments = fields.One2Many('collection.assignment', None, 'Assignments',
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


class CollectionWizard(model.CoopWizard):
    'Collection Wizard'

    __name__ = 'collection.collection_wizard'

    start_state = 'input_collection_parameters'
    input_collection_parameters = StateView('collection.collection_parameters',
        'collection.collection_parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Assign', 'assign', 'tryton-go-next')])
    assign = StateView('collection.assign_collection',
        'collection.assign_collection_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'check_amount', 'tryton-ok')])
    check_amount = StateTransition()
    validate = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CollectionWizard, cls).__setup__()
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
            'remaining': self.input_collection_parameters.amount}

    def transition_check_amount(self):
        if self.assign.create_suspense_line_with_rest:
            return 'validate'
        amount = self.input_collection_parameters.amount
        ventilated_amount = sum(map(lambda x: x.amount,
                self.assign.assignments))
        if amount != ventilated_amount:
            self.raise_user_error('bad_ventilation', (amount,
                    ventilated_amount))
        return 'validate'

    def transition_validate(self):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Company = pool.get('company.company')
        Date = pool.get('ir.date')
        Collection = pool.get('collection.collection')
        Payment = pool.get('account.payment')
        PaymentGroup = pool.get('account.payment.group')
        company = Company(Transaction().context.get('company'))
        collection_move = Move()
        collection_move.journal = company.collection_journal
        collection_move.date = Date.today()
        collection_move.lines = []
        remaining = self.assign.amount
        payments = []
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
        if payments:
            payment_group = PaymentGroup()
            payment_group.company = company
            payment_group.journal = company.get_payment_journal(
                company.currency)
            payment_group.kind = 'receivable'
            payment_group.payments = payments
            payment_group.save()
        collection_line = MoveLine()
        collection_line.party = self.assign.party
        collection_line.debit = self.input_collection_parameters.amount
        collection_line.account = getattr(company, '%s_account' %
            self.input_collection_parameters.kind)
        collection_move.lines.append(collection_line)
        collection_move.save()
        Move.post([collection_move])
        log = Collection()
        log.party = self.input_collection_parameters.party
        log.amount = self.input_collection_parameters.amount
        log.kind = self.input_collection_parameters.kind
        log.assignment_move = collection_move
        if self.input_collection_parameters.check_number:
            log.check_number = self.input_collection_parameters.check_number
        log.save()
        return 'end'

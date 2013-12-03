import copy

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button, StateTransition

from trytond.modules.coop_utils import fields, model, export


__all__ = [
    'Configuration',
    'SuspenseParty',
    'Collection',
    'Payment',
    'CollectionParameters',
    'Assignment',
    'AssignCollection',
    'CollectionWizard',
    ]


class Configuration(export.ExportImportMixin):
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
    cash_account = fields.Property(
        fields.Many2One('account.account', 'Cash Account',
            domain=[('kind', '=', 'revenue')]))
    check_account = fields.Property(
        fields.Many2One('account.account', 'Check Account',
            domain=[('kind', '=', 'revenue')]))
    collection_journal = fields.Property(
        fields.Many2One('account.journal', 'Journal', domain=[
                ('type', '=', 'cash')]))

    @classmethod
    def _export_keys(cls):
        # Account Configuration is a singleton, so the id is an acceptable
        # key
        return set(['id'])

    @classmethod
    def _export_must_export_field(cls, field_name, field):
        # Function field are not exported by default
        if field_name in ('default_account_receivable',
                'default_account_payable', 'default_suspense_account'):
            return True
        return super(Configuration, cls)._export_must_export_field(
            field_name, field)

    def _export_default_account(self, name, exported, result, my_key):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        company_id = Transaction().context.get('company')
        account_field, = ModelField.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', name[8:]),
            ], limit=1)
        properties = Property.search([
            ('field', '=', account_field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ], limit=1)
        if properties:
            prop, = properties
            prop._export_json(exported, result)
        return None

    def _export_override_default_account_receivable(self, exported, result,
            my_key):
        return self._export_default_account('default_account_receivable',
            exported, result, my_key)

    def _export_override_default_account_payable(self, exported, result,
            my_key):
        return self._export_default_account('default_account_payable',
            exported, result, my_key)

    def _export_override_default_suspense_account(self, exported, result,
            my_key):
        return self._export_default_account('default_suspense_account',
            exported, result, my_key)

    @classmethod
    def _import_default_account(cls, name, instance_key, good_instance,
            field_value, values, created, relink):
        if not field_value:
            return
        _account_field, _company, _value = field_value


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

    @classmethod
    def __setup__(cls):
        super(SuspenseParty, cls).__setup__()
        cls.suspense_account = copy.copy(cls.suspense_account)
        cls.suspense_account.domain = export.clean_domain_for_import(
            cls.suspense_account.domain, 'company')


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
    check_reception_date = fields.Date('Check Reception Date', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check'})

    def get_create_user(self, name):
        return self.create_uid.id


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    collection = fields.Many2One('collection.collection', 'Collection')


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
    check_reception_date = fields.Date('Check Reception Date', states={
            'invisible': Eval('kind') != 'check',
            'required': Eval('kind') == 'check'})
    collection = fields.Many2One('collection.collection', 'Collection',
        states={'invisible': True})


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

    amount = fields.Numeric('Amount')
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
        Collection = pool.get('collection.collection')
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

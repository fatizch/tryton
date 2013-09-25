from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button, StateTransition

from trytond.modules.coop_utils import fields, model


__all__ = [
    'Company',
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


class Collection(model.CoopSQL, model.CoopView):
    'Assignment Log'

    __name__ = 'collection.assignment_log'

    amount = fields.Numeric('Numeric', states={'readonly': True})
    kind = fields.Selection([('cash', 'Cash'), ('check', 'Check')], 'Kind',
        states={'readonly': True})
    assignment_move = fields.Many2One('account.move', 'Assignment Move',
        states={'readonly': True})
    party = fields.Many2One('party.party', 'Party', states={'readonly': True})
    create_user = fields.Function(
        fields.Many2One('res.user', 'Created by', states={'readonly': True}),
        'get_create_user')

    def get_create_user(self, name):
        return self.create_uid


class CollectionParameters(model.CoopView):
    'Collection parameters'

    __name__ = 'collection.collection_parameters'

    kind = fields.Selection([('cash', 'Cash'), ('check', 'Check')], 'Kind',
        required=True)
    amount = fields.Numeric('Amount', required=True)
    party = fields.Many2One('party.party', 'Party', required=True)


class Assignment(model.CoopView):
    'Assignment'

    __name__ = 'collection.assignment'

    amount = fields.Numeric('Amount', on_change_with=['source_move_line'])
    source_move_line = fields.Many2One('account.move.line', 'Source Move Line',
        states={'invisible': Eval('kind') != 'move_line'}, domain=[
            ('party', '=', Eval('context', {}).get('from_party')),
            ('account.kind', '=', 'receivable'),
            ('move.state', '=', 'posted')])
    target_account = fields.Many2One('account.account', 'Target Account',
        required=True, on_change_with=['source_move_line'],
        domain=[('kind', '=', 'receivable'), ('move.state', '=', 'posted')])
    kind = fields.Selection([
            ('move_line', 'From Move Line'),
            ('select_account', 'Select Account')],
        'Kind', on_change=['kind', 'source_move_line', 'target_account'])

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
        return self.source_move_line.credit

    @classmethod
    def default_kind(cls):
        return 'move_line'


class AssignCollection(model.CoopView):
    'Assign Collection'

    __name__ = 'collection.assign_collection'

    amount = fields.Numeric('Amount', states={'readonly': True})
    party = fields.Many2One('party.party', 'party')
    assignments = fields.One2Many('collection.assignment', None, 'Assignments',
        context={'from_party': Eval('party')}, depends=['party'])


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

    def default_assign(self, name):
        return {
            'party': self.input_collection_parameters.party.id,
            'amount': self.input_collection_parameters.amount}

    def transition_check_amount(self):
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
        company = Company(Transaction().context.get('company'))
        collection_move = Move()
        collection_move.journal = company.collection_journal
        collection_move.date = Date.today()
        collection_move.lines = []
        for line in self.assign.assignments:
            new_line = MoveLine()
            new_line.account = line.target_account
            new_line.party = self.assign.party
            new_line.debit = line.amount
            collection_move.lines.append(new_line)
        collection_line = MoveLine()
        collection_line.party = self.assign.party
        collection_line.credit = self.input_collection_parameters.amount
        collection_line.account = getattr(company, '%s_account' %
            self.input_collection_parameters.kind)
        collection_move.lines.append(collection_line)
        collection_move.save()
        log = Collection()
        log.party = self.input_collection_parameters.partyy
        log.amount = self.input_collection_parameters.amount
        log.kind = self.input_collection_parameters.kind
        log.assignment_move = collection_move
        log.save()
        return 'end'

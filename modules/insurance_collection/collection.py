from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, If

from trytond.modules.coop_utils import fields


__all__ = [
    'CollectionParameters',
    'AssignCollection',
    'CollectionWizard',
    ]


class CollectionParameters():
    'Collection parameters'

    __metaclass__ = PoolMeta
    __name__ = 'collection.create.parameters'

    contract = fields.Many2One('contract.contract', 'Contract', on_change=[
            'contract', 'party'], depends=['party'], domain=[
                If(~Eval('party'),
                    ('id', '!=', 0),
                    ('subscriber', '=', Eval('party')))])

    def on_change_contract(self):
        if not (hasattr(self, 'contract') and self.contract):
            return {}
        return {'party': self.contract.subscriber.id}


class AssignCollection():
    'Assign Collection'

    __metaclass__ = PoolMeta
    __name__ = 'collection.create.assign'

    contract = fields.Many2One('contract.contract', 'Contract',
        states={'readonly': True})


class CollectionWizard():
    'Collection Wizard'

    __metaclass__ = PoolMeta
    __name__ = 'collection.collection_wizard'

    def default_input_collection_parameters(self, name):
        res = super(
            CollectionWizard, self).default_input_collection_parameters(name)
        if Transaction().context.get('active_model') == 'contract.contract':
            Contract = Pool().get('contract.contract')
            res['contract'] = Transaction().context.get('active_id')
            res['party'] = Contract(res['contract']).subscriber.id
        return res

    def default_assign(self, name):
        MoveLine = Pool().get('account.move.line')
        res = super(CollectionWizard, self).default_assign(name)
        if not self.input_collection_parameters.contract:
            return res
        res['contract'] = self.input_collection_parameters.contract.id
        line_candidates = MoveLine.search([
                ('move.origin', '=', (
                        'contract.contract',
                        self.input_collection_parameters.contract.id)),
                ('party', '=', self.input_collection_parameters.party),
                ('account.kind', '=', 'receivable'),
                ('move.state', '=', 'posted')], order=[('maturity_date',
                    'ASC')])
        if not line_candidates:
            return res
        exact = False
        remaining = self.input_collection_parameters.amount
        selected = []
        for line in line_candidates:
            if self.input_collection_parameters.amount == line.debit:
                exact = True
                selected = [line]
                break
            if remaining <= 0:
                continue
            selected.append(line)
            remaining -= line.debit
        if exact:
            res['assignments'] = [{
                    'amount': self.input_collection_parameters.amount,
                    'source_move_line': selected[0].id,
                    'kind': 'move_line',
                    'target_account': selected[0].account.id,
                    }]
            res['remaining'] = 0
        else:
            res['assignments'] = []
            remaining_done = remaining >= 0
            for line in reversed(selected):
                new_assignment = {
                    'source_move_line': line.id,
                    'kind': 'move_line',
                    'target_account': line.account.id,
                    }
                if not remaining_done:
                    new_assignment['amount'] = line.debit + remaining
                    remaining_done = True
                else:
                    new_assignment['amount'] = line.debit
                res['assignments'].append(new_assignment)
            res['remaining'] = remaining if remaining > 0 else 0
            if res['remaining']:
                res['create_suspense_line_with_rest'] = True
        return res

    def get_collection_move(self):
        result = super(CollectionWizard, self).get_collection_move()
        if not self.input_collection_parameters.contract:
            return result
        result.origin = self.input_collection_parameters.contract
        return result

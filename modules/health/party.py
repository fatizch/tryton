from trytond.pool import PoolMeta
from trytond.pyson import Eval, And
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, fields

__all__ = [
    'Party',
    'PartyHealthComplement',
    ]


class Party():
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health')
    health_complement = fields.One2Many('health.party_complement', 'party',
        'Health Complement', size=1, states={
            'invisible': And(~Eval('health_complement'), ~Eval('is_health'))})
    health_contract = fields.Function(
        fields.Many2One('contract', 'Health Contract', states={
                'invisible': Eval('context', {}).get('synthesis') != 'health',
                }), 'get_health_contract_id')

    def get_is_health(self, name):
        return Transaction().context.get('is_health')

    @classmethod
    def default_health_complement(cls):
        if Transaction().context.get('is_health'):
            return [{}]
        return []

    def get_health_contract_id(self, name):
        for contract in self.contracts:
            if contract.is_health:
                return contract.id


class PartyHealthComplement(model.CoopSQL, model.CoopView):
    'Party Health Complement'

    __name__ = 'health.party_complement'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE')

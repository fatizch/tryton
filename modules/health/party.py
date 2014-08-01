from trytond.pool import PoolMeta
from trytond.pyson import Eval, And
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields, coop_string

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'HealthPartyComplement',
    ]


class Party:
    __name__ = 'party.party'

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

    @classmethod
    def search_rec_name(cls, name, clause):
        return [
            'OR',
            [('first_name',) + tuple(clause[1:])],
            [('name',) + tuple(clause[1:])],
            [('ssn',) + tuple(clause[1:])]
        ]

    def get_rec_name(self, name):
        if self.is_person:
            return "[%s] %s %s %s " % (self.ssn, coop_string.translate_value(
                self, 'gender'), self.name.upper(), self.first_name)
        return super(Party, self).get_rec_name(name)


class HealthPartyComplement(model.CoopSQL, model.CoopView):
    'Health Party Complement'

    __name__ = 'health.party_complement'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE')

from trytond.pool import PoolMeta
from trytond.pyson import Eval
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
        'Health Complement', size=1, states={'invisible': ~Eval('is_health')})

    def get_is_health(self, name):
        return Transaction().context.get('is_health')


class PartyHealthComplement(model.CoopSQL, model.CoopView):
    'Party Health Complement'

    __name__ = 'health.party_complement'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE')

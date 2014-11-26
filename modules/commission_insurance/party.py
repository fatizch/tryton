from trytond.pool import PoolMeta
from trytond.pyson import Not, Eval, Bool, If

from trytond.modules.cog_utils import fields, model
from trytond.modules.party_cog.party import STATES_COMPANY

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'Broker',
    ]


class Party:
    __name__ = 'party.party'

    broker_role = fields.One2Many('broker', 'party', 'Broker', size=1,
        states={'invisible': ~Eval('is_broker', False) | Not(STATES_COMPANY)},
        depends=['is_broker', 'is_company'])
    is_broker = fields.Function(
        fields.Boolean('Is Broker',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')
    agents = fields.One2Many('commission.agent', 'party', 'Agents',
        depends=['is_broker', 'is_insurer'],
        domain=[If(Bool(Eval('is_broker')),
                [('type_', '=', 'agent')], []),
            If(Bool(Eval('is_insurer')),
                [('type_', '=', 'principal')], [])])

    @fields.depends('is_broker')
    def on_change_is_broker(self):
        self._on_change_is_actor('is_broker')


class Broker(model.CoopSQL, model.CoopView):
    'Broker'

    __name__ = 'broker'
    _rec_name = 'party'

    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', select=True)

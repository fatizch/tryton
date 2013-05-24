from trytond.pool import PoolMeta

from trytond.modules.coop_utils import model, fields

__all__ = [
    'Party',
    'Broker',
]


class Party:
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    broker_role = fields.One2Many('party.broker', 'party', 'Broker', size=1)
    dist_networks = fields.Many2Many('distribution.dist_network-broker',
        'broker', 'dist_network', 'Distribution Networks')

    @classmethod
    def _export_force_recreate(cls):
        result = super(Party, cls)._export_force_recreate()
        result.remove('broker_role')
        return result


class Broker(model.CoopSQL, model.CoopView):
    'Broker'

    __name__ = 'party.broker'

    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', select=True)
    reference = fields.Char('Reference')

    @classmethod
    def get_summary(cls, brokers, name=None, at_date=None, lang=None):
        return dict([(broker.id, 'X') for broker in brokers])

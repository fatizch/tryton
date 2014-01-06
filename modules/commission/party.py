from trytond.pool import PoolMeta

from trytond.modules.coop_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'Broker',
    ]


class Party:
    __name__ = 'party.party'

    broker_role = fields.One2Many('broker', 'party', 'Broker', size=1)
    dist_networks = fields.Many2Many('distribution.network-broker',
        'broker', 'dist_network', 'Distribution Networks')

    @classmethod
    def _export_force_recreate(cls):
        result = super(Party, cls)._export_force_recreate()
        result.remove('broker_role')
        return result

    @classmethod
    def _export_skips(cls):
        result = super(Party, cls)._export_skips()
        result.add('dist_networks')
        return result


class Broker(model.CoopSQL, model.CoopView):
    'Broker'

    __name__ = 'broker'

    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', select=True)
    reference = fields.Char('Reference')

    @classmethod
    def get_summary(cls, brokers, name=None, at_date=None, lang=None):
        return dict([(broker.id, 'X') for broker in brokers])

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])

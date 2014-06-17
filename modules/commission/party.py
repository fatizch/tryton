from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'Broker',
    ]


class Party:
    __name__ = 'party.party'

    broker_role = fields.One2Many('broker', 'party', 'Broker', size=1)

    @classmethod
    def _export_force_recreate(cls):
        result = super(Party, cls)._export_force_recreate()
        result.remove('broker_role')
        return result


class Broker(model.CoopSQL, model.CoopView):
    'Broker'

    __name__ = 'broker'
    _rec_name = 'party'

    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', select=True)
    reference = fields.Char('Reference')
    dist_networks = fields.Many2Many('distribution.network-broker',
        'broker', 'dist_network', 'Distribution Networks')

    @classmethod
    def get_summary(cls, brokers, name=None, at_date=None, lang=None):
        return dict([(broker.id, 'X') for broker in brokers])

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])

    @classmethod
    def _export_skips(cls):
        result = super(Broker, cls)._export_skips()
        result.add('dist_networks')
        return result

    def get_rec_name(self, name):
        return '[%s] %s' % (self.reference,
            self.party.rec_name if self.party else '')

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('reference',) + tuple(clause[1:])],
            [('party.name',) + tuple(clause[1:])],
            [('party.short_name',) + tuple(clause[1:])],
            ]

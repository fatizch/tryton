from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    network = fields.One2Many('distribution.network', 'party', 'Network')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [(
                '/form/notebook/page[@name="network"]',
                'states',
                {'invisible': ~Eval('network')}
                )]

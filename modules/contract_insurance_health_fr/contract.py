from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'CoveredElement',
    ]


class CoveredElement:
    __name__ = 'contract.covered_element'

    is_rsi = fields.Function(
        fields.Boolean('Is RSI', states={'invisible': True}),
        'on_change_with_is_rsi')
    is_law_madelin = fields.Boolean('Law Madelin',
        states={'invisible': ~Eval('is_rsi')})

    @fields.depends('party')
    def on_change_with_is_rsi(self, name=None):
        if self.party and self.party.health_complement:
            hc_system = self.party.health_complement[0].hc_system
            return hc_system.code == '03' if hc_system else False
        return False

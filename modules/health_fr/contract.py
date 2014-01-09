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
        fields.Boolean('Is RSI', on_change_with=['party'],
            states={'invisible': True}),
        'on_change_with_is_rsi')
    is_law_madelin = fields.Boolean('Law Madelin',
        states={'invisible': ~Eval('is_rsi')})

    def on_change_with_is_rsi(self, name=None):
        if self.party and self.party.health_complement:
            regime = self.party.health_complement[0].regime
            return regime.code == '03' if regime else False
        return False

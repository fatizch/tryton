from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.coop_utils import fields

__all__ = [
    'PartyHealthComplement',
    ]


class PartyHealthComplement():
    'Party Health Complement'

    __name__ = 'health.party_complement'
    __metaclass__ = PoolMeta

    department = fields.Function(
        fields.Char('Department'),
        'get_department', 'set_void')
    regime = fields.Many2One('health.regime', 'Regime')
    insurance_fund = fields.Many2One('health.insurance_fund', 'Insurance Fund',
        domain=[
            [If(
                    ~Eval('department'),
                    (),
                    ('department', '=', Eval('department')),
                    )],
            ('regime', '=', Eval('regime')),
            ], depends=['department', 'regime'])

    def get_department(self, name):
        address = self.party.address_get() if self.party else None
        return address.get_department() if address else ''

    @classmethod
    def set_void(cls, instances, vals, name):
        pass

from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'HealthPartyComplement',
    ]


class HealthPartyComplement:
    __name__ = 'health.party_complement'

    department = fields.Function(
        fields.Char('Department'),
        'get_department', 'set_void')
    hc_system = fields.Many2One('health.care_system', 'Health Care System')
    insurance_fund = fields.Many2One('health.insurance_fund', 'Insurance Fund',
        domain=[
            [If(
                    ~Eval('department'),
                    (),
                    ('department', '=', Eval('department')),
                    )],
            ('hc_system', '=', Eval('hc_system')),
            ], depends=['department', 'hc_system'])

    def get_department(self, name):
        address = self.party.address_get() if self.party else None
        return address.get_department() if address else None

    @classmethod
    def set_void(cls, instances, vals, name):
        pass

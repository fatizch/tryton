import copy
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields, utils

__all__ = [
    'Contract',
    'Option',
    'CoveredElement',
    ]


class Contract():
    'Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health')

    def get_is_health(self, name):
        if not self.options and self.offered:
            return self.offered.is_health
        for option in self.options:
            if option.is_health:
                return True
        return False


class Option():
    'Option'

    __name__ = 'contract.subscribed_option'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health')

    def get_is_health(self, name=None):
        return self.offered and self.offered.is_health


class CoveredElement():
    'Covered Element'

    __name__ = 'ins_contract.covered_element'
    __metaclass__ = PoolMeta

    health_complement = fields.Function(
        fields.One2Many('health.party_complement', None, 'Health Complement',
            on_change_with=['party']),
        'get_health_complement', 'set_health_complement')

    @classmethod
    def __setup__(cls):
        super(CoveredElement, cls).__setup__()
        cls.party = copy.copy(cls.party)
        if not cls.party.context:
            cls.party.context = {}
        cls.party.context['is_health'] = Eval('_parent_contract',
            {}).get('is_health')

    @classmethod
    def create(cls, values):
        pool = Pool()
        Contract = pool.get('contract.contract')
        Health_Complement = pool.get('health.party_complement')
        Party = pool.get('party.party')
        health_complements = []
        for covered_element in values:
            if utils.is_none(Contract(covered_element['contract']),
                    'is_health'):
                continue
            party = Party(covered_element['party'])
            if party.is_person and not party.health_complement:
                health_complements.append({'party': covered_element['party']})
        if health_complements:
            Health_Complement.create(health_complements)
        return super(CoveredElement, cls).create(values)

    def get_health_complement(self, name):
        return ([x.id for x in self.party.health_complement]
            if self.party else [])

    def on_change_with_health_complement(self, name=None):
        if not self.party:
            return []
        elif self.party and not self.party.health_complement:
            address = self.party.address_get() if self.party else None
            department = address.get_department() if address else ''
            return {'add': [{
                        'party': self.party.id,
                        'department': department}]}
        else:
            return [x.id for x in self.party.health_complement]

    @classmethod
    def set_health_complement(cls, instances, name, vals):
        Health_Complement = Pool().get('health.party_complement')
        for action in vals:
            if action[0] == 'write':
                Health_Complement.write(
                    [Health_Complement(x) for x in action[1]],
                    action[2])
            elif action[0] == 'create':
                Health_Complement.create(action[1])

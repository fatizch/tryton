# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'Option',
    'CoveredElement',
    ]


class Contract:
    __name__ = 'contract'

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health', searcher='search_is_health')

    def get_is_health(self, name):
        if self.product:
            return self.product.is_health
        return False

    @classmethod
    def search_is_health(cls, name, clause):
        return [('product.is_health',) + tuple(clause[1:])]


class Option:
    __name__ = 'contract.option'

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health')

    def get_is_health(self, name=None):
        return self.product and self.product.is_health


class CoveredElement:
    __name__ = 'contract.covered_element'

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health')
    health_complement = fields.Function(
        fields.One2Many('health.party_complement', None, 'Health Complement',
            states={'invisible': Or(~Eval('is_health'), ~Eval('is_person'))}),
        'get_health_complement', 'set_health_complement')

    @classmethod
    def create(cls, values):
        pool = Pool()
        Contract = pool.get('contract')
        Health_Complement = pool.get('health.party_complement')
        Party = pool.get('party.party')
        CovElement = pool.get('contract.covered_element')
        health_complements = []
        for cov_dict in values:
            contract = None
            if 'main_contract' in cov_dict and cov_dict['main_contract']:
                contract = Contract(cov_dict['main_contract'])
            elif 'parent' in cov_dict and cov_dict['parent']:
                contract = CovElement(cov_dict['parent']).main_contract
            elif 'contract' in cov_dict and cov_dict['contract']:
                contract = Contract(cov_dict['contract'])
            if not contract.is_health or 'party' not in cov_dict:
                continue
            if not cov_dict['party']:
                continue
            party = Party(cov_dict['party'])
            if party.is_person and not party.health_complement:
                health_complements.append({'party': cov_dict['party']})
        if health_complements:
            Health_Complement.create(health_complements)
        return super(CoveredElement, cls).create(values)

    def get_health_complement(self, name):
        return ([x.id for x in self.party.health_complement]
            if self.party else [])

    @fields.depends('party', 'is_health', 'is_person')
    def on_change_with_health_complement(self, name=None):
        if not self.party or not self.is_person:
            return []
        elif (self.is_person and self.is_health
                and not self.party.health_complement):
            address = self.party.address_get() if self.party else None
            department = address.get_department() if address else ''
            return {'add': [(-1, {
                        'party': self.party.id,
                        'department': department})]}
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

    def get_is_health(self, name):
        return self.main_contract.is_health if self.main_contract else False

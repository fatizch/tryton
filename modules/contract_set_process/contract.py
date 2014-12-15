from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'ContractSet',
    ]


class ContractSet(CogProcessFramework):
    __name__ = 'contract.set'
    __metaclass__ = ClassAttr

    covered_parties = fields.Function(
        fields.One2Many('party.party', None, 'Covered Parties'),
        'get_covered_parties')
    party_relations = fields.Function(
        fields.One2Many('party.relation.all', None, 'Party Relations',
            depends=['covered_parties'],
            domain=['OR',
                [('from_', 'in', Eval('covered_parties'))],
                [('to', 'in', Eval('covered_parties'))]
                ]),
        'get_party_relations', setter='set_party_relations')

    def get_party_relations(self, name):
        parties = []
        for contract in self.contracts:
            parties.extend(covered.party for covered in
                contract.covered_elements)
        parties = list(set(parties))
        return [relation.id for party in parties
            for relation in party.relations]

    @classmethod
    def set_party_relations(cls, objects, name, values):
        pool = Pool()
        relation = pool.get('party.relation.all')
        res = []
        for value in values:
            if value[0] == 'create':
                res.extend(value[1])
        if res:
            return relation.create(res)
        else:
            return []

    def get_covered_parties(self, name):
        parties = []
        for contract in self.contracts:
            parties.extend(covered.party for covered in
                contract.covered_elements)
        parties = list(set(parties))
        res = [party.id for party in parties]
        return res

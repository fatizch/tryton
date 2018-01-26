# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'HealthPartyComplement',
    'PartyReplace'
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    health_complement = fields.One2Many('health.party_complement', 'party',
        'Health Complement', delete_missing=True,
        states={'invisible': ~Eval('is_person')},
        depends=['is_person'])
    health_contract = fields.Function(
        fields.Many2One('contract', 'Health Contract', states={
                'invisible': Eval('context', {}).get('synthesis') != 'health',
                }), 'get_health_contract_id')
    birth_order = fields.Integer('Birth Order')

    def get_health_contract_id(self, name):
        for contract in self.contracts:
            if contract.is_health:
                return contract.id

    @classmethod
    def search_rec_name(cls, name, clause):
        domain = super(Party, cls).search_rec_name(name, clause)
        if domain[0] == 'OR':
            domain.append([('ssn',) + tuple(clause[1:])])
        return domain

    def get_rec_name(self, name):
        name = super(Party, self).get_rec_name(name)
        if self.is_person and self.ssn:
            name += " - %s" % self.ssn
        return name

    def get_health_complement_at_date(self, at_date=None):
        return utils.get_good_version_at_date(self, 'health_complement',
            at_date)


class HealthPartyComplement(model._RevisionMixin, model.CoogSQL,
        model.CoogView):
    'Health Party Complement'

    __name__ = 'health.party_complement'
    _func_key = 'date'
    _parent_name = 'party'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        required=True, select=True)

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['date'] if 'date' in values else None


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('health.party_complement', 'party'),
            ]

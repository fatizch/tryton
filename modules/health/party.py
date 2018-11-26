# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields, utils
from trytond.modules.party_cog.party import STATES_PERSON, STATES_ACTIVE

__all__ = [
    'Party',
    'HealthPartyComplement',
    'PartyReplace'
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    health_complement = fields.One2Many('health.party_complement', 'party',
        'Health Complement', delete_missing=True,
        states={'invisible': ~STATES_PERSON, 'readonly': STATES_ACTIVE},
        depends=['is_person', 'active'])
    health_contract = fields.Function(
        fields.Many2One('contract', 'Health Contract', states={
                'invisible': Eval('context', {}).get('synthesis') != 'health',
                }), 'get_health_contract_id')
    birth_order = fields.Integer('Birth Order',
        states={'invisible': ~STATES_PERSON, 'readonly': STATES_ACTIVE},
        depends=['is_person', 'active'])

    def get_health_contract_id(self, name):
        for contract in self.contracts:
            if contract.is_health:
                return contract.id

    def get_health_complement_at_date(self, at_date=None):
        return utils.get_good_version_at_date(self, 'health_complement',
            at_date, start_var_name='date')


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


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('health.party_complement', 'party'),
            ]

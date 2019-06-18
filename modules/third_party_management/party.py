# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.pyson import Not

from trytond.modules.coog_core import model, fields
from trytond.modules.party_cog.party import STATES_COMPANY


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    third_party_manager_role = fields.One2Many(
        'third_party_manager', 'party', "Third Party Role",
        delete_missing=True)
    is_third_party_manager = fields.Function(
        fields.Boolean("Is Third-Party Manager",
            states={
                'invisible': Not(STATES_COMPANY),
                },
            depends=['is_person']),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')

    def non_customer_clause(cls, clause):
        domain = super().non_customer_clause(clause)
        additional_clause = []
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[2]:
            if clause[1] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [
                ('is_third_party_manager', clause[1], False)]
        else:
            if reverse[clause[1]] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [
                ('is_third_party_manager', reverse[clause[1]], False)]
        return additional_clause + domain

    @fields.depends('is_third_party_manager')
    def on_change_is_third_party_manager(self):
        self._on_change_is_actor('is_third_party_manager')


class ThirdPartyManager(model.CoogView, model.CoogSQL):
    'Third Party Manager'

    __name__ = 'third_party_manager'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    party = fields.Many2One('party.party', "Third Party Manager",
        domain=[
            ('is_third_party_manager', '=', True),
            ],
        ondelete='RESTRICT', required=True)

    def get_rec_name(self, name):
        if self.party:
            return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]

    def get_func_key(self, name):
        return self.party.code

    @classmethod
    def search_func_key(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

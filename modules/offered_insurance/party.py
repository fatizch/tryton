from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not

from trytond.modules.cog_utils import model, fields, coop_string
from trytond.modules.party_cog.party import STATES_COMPANY

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'Insurer',
    ]


class Party:
    __name__ = 'party.party'

    insurer_role = fields.One2Many('insurer', 'party', 'Insurer', size=1,
        states={'invisible': ~Eval('is_insurer', False) | Not(STATES_COMPANY)},
        depends=['is_insurer', 'is_company'])
    is_insurer = fields.Function(
        fields.Boolean('Is Insurer',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')

    @fields.depends('is_insurer')
    def on_change_is_insurer(self):
        self._on_change_is_actor('is_insurer')

    @classmethod
    def _export_force_recreate(cls):
        result = super(Party, cls)._export_force_recreate()
        result.remove('insurer_role')
        return result

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = super(Party, cls).get_summary(
            parties, name=name, at_date=at_date, lang=lang)
        for party in parties:
            if party.insurer_role:
                res[party.id] += coop_string.get_field_as_summary(party,
                    'insurer_role', True, at_date, lang=lang)
        return res

    def get_rec_name(self, name):
        if self.is_insurer:
            return self.name
        else:
            return super(Party, self).get_rec_name(name)


class Insurer(model.CoopView, model.CoopSQL):
    'Insurer'

    __name__ = 'insurer'
    _rec_name = 'party'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    party = fields.Many2One('party.party', 'Insurer', ondelete='CASCADE')

    def get_func_key(self, name):
        return self.party.code

    @classmethod
    def search_func_key(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])

    @classmethod
    def get_summary(cls, insurers, name=None, at_date=None, lang=None):
        return dict([(insurer.id, 'X') for insurer in insurers])

    def get_rec_name(self, name):
        return (self.party.rec_name
            if self.party else super(Insurer, self).get_rec_name(name))

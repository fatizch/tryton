# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not, Bool

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

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ('/form/notebook/page[@id="role"]/notebook/page[@id="insurer"]',
                'states', {'invisible': Bool(~Eval('is_insurer'))}),
            ]

    @fields.depends('is_insurer')
    def on_change_is_insurer(self):
        self._on_change_is_actor('is_insurer')

    def get_summary_content(self, label, at_date=None, lang=None):
        res = super(Party, self).get_summary_content(label, at_date, lang)
        if self.insurer_role:
            res[1].append(coop_string.get_field_summary(self, 'insurer_role',
                True, at_date, lang))
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
    party = fields.Many2One('party.party', 'Insurer', ondelete='RESTRICT',
        required=True)

    def get_func_key(self, name):
        return self.party.code

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def search_func_key(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

    def get_summary_content(self, labelTrue, at_date=None, lang=None):
        return (self.rec_name, 'X')

    def get_rec_name(self, name):
        return (self.party.rec_name
            if self.party else super(Insurer, self).get_rec_name(name))

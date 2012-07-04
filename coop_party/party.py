#-*- coding:utf-8 -*-
import functools
import copy

from trytond.model import fields as fields
from trytond.pyson import Eval

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils, CoopView, CoopSQL

__all__ = ['Party', 'Actor', 'PersonRelations', 'Person', 'LegalEntity']
__metaclass__ = PoolMeta

GENDER = [('M', 'Mr.'),
          ('F', 'Mrs.'),
            ]


class Party:
    'Party'

    __name__ = 'party.party'

    person = fields.One2Many('party.person', 'party', 'Person', size=1)
    legal_entity = fields.One2Many('party.legal_entity',
        'party', 'Legal Entity', size=1)
    is_legal_entity = fields.Function(fields.Boolean('Legal entity'),
        'get_is_actor')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._sql_constraints.remove(('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique!'))

    @staticmethod
    def default_addresses():
        #RSE 03/07/2012 Temporary fix for xml import. See issue B-529
        return ''


class Actor(CoopView):
    'Actor'
    _inherits = {'party.party': 'party'}
    __name__ = 'party.actor'
    _rec_name = 'reference'

    reference = fields.Char('Reference')
    party = fields.Many2One('party.party', 'Party',
                    required=True, ondelete='CASCADE', select=True)


class PersonRelations(CoopSQL, CoopView):
    'Person Relations'

    __name__ = 'party.person-relations'

    from_person = fields.Many2One('party.person', 'From Person')
    to_person = fields.Many2One('party.person', 'From Person')
    kind = fields.Selection('get_relation_kind', 'Kind')
    reverse_kind = fields.Function(fields.Char('Reverse Kind',
            readonly=True,
            on_change_with=['kind']),
        'get_reverse_kind')

    @staticmethod
    def get_relation_kind():
        return utils.get_dynamic_selection('person_relation')

    def get_reverse_kind(self, name):
        reverse_values = utils.get_reverse_dynamic_selection(self.kind)
        if len(reverse_values) > 0:
            return reverse_values[0][1]
        return ''

    def on_change_with_reverse_kind(self, name):
        return self.get_reverse_kind(name)


class Person(CoopSQL, Actor):
    'Person'

    __name__ = 'party.person'

    gender = fields.Selection(GENDER, 'Gender',
        required=True,
        on_change=['gender'])
    first_name = fields.Char('First Name', required=True)
    maiden_name = fields.Char('Maiden Name',
        states={'readonly': Eval('gender') != 'F'},
        depends=['gender'])
    birth_date = fields.Date('Birth Date', required=True)
    ssn = fields.Char('SSN')
    relations = fields.One2Many('party.person-relations',
                                 'from_person', 'Relations')
    in_relation_with = fields.One2Many('party.person-relations',
                                 'to_person', 'in relation with')

    def get_rec_name(self, name):
        return "%s %s" % (self.name.upper(), self.first_name)

    def on_change_gender(self):
        res = {}
        if self.gender == 'F':
            return res
        res['maiden_name'] = ''
        return res


class LegalEntity(CoopSQL, Actor):
    'Legal Entity'

    __name__ = 'party.legal_entity'

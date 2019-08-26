# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.model import Unique
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import fields, coog_string, utils
from trytond.modules.party_cog.party import STATES_PERSON, STATES_ACTIVE

SSN_LENGTH = 15

__all__ = [
    'Party',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    ssn = fields.EmptyNullChar('SSN', states={
            'invisible': ~STATES_PERSON,
            'readonly': STATES_ACTIVE,
            'required': Eval('ssn_required', False)
            }, depends=['is_person', 'ssn_required', 'active'])
    ssn_required = fields.Function(fields.Boolean('SSN Required'),
        'get_SSN_required')
    ssn_no_key = fields.Function(fields.Char('SSN', size=13, states={
                'invisible': ~STATES_PERSON,
                'readonly': STATES_ACTIVE,
                }, depends=['active', 'is_person']),
        'get_ssn', setter='set_ssn')
    ssn_key = fields.Function(fields.Char('SSN Key', size=2, states={
                'invisible': ~STATES_PERSON,
                'readonly': STATES_ACTIVE,
                }, depends=['active', 'is_person']),
        'get_ssn', setter='set_ssn')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('SSN_uniq', Unique(t, t.ssn),
             'The SSN of the party must be unique.')]

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        for party in parties:
            party.check_ssn()
            party.check_ssn_key()

    def get_rec_name(self, name):
        if self.ssn:
            return '[%s] %s - %s' % (self.code, self.full_name, self.ssn)
        else:
            return super(Party, self).get_rec_name(name)

    def get_synthesis_rec_name(self, name):
        res = super(Party, self).get_synthesis_rec_name(name)
        if self.is_person and self.ssn:
            res += ' (%s)' % self.ssn
        return res

    def get_summary_content(self, label, at_date=None, lang=None):
        label, value = super(Party, self).get_summary_content(label, at_date,
            lang)
        if self.is_person:
            value.insert(0, coog_string.get_field_summary(self, 'ssn', True,
                at_date, lang))
        return label, value

    @classmethod
    def get_key_for_search_rec_name_domain(cls):
        return super(Party, cls).get_key_for_search_rec_name_domain() + ['ssn']

    def get_SSN_required(self, name):
        return False

    @classmethod
    def get_values_to_erase(cls):
        res = super(Party, cls).get_values_to_erase()
        res.update({'ssn': None})
        return res

    @staticmethod
    def calculate_ssn_key(ssn_no_key):
        ssn_as_num = str(ssn_no_key).replace('2A', '19').replace('2B', '18')
        key = 97 - int(ssn_as_num) % 97
        return key

    def check_ssn(self):
        if not self.ssn:
            res = True
        else:
            pattern = """^[12345678]
                [0-9]{2}
                [0-9][0-9]
                (2[AB]|[0-9]{2})
                [0-9]{3}
                [0-9]{3}
                [0-9]{2}$"""
            res = re.search(pattern, self.ssn, re.X)
        if not res:
            raise ValidationError(gettext('party_ssn.msg_invalid_ssn'))

    def check_ssn_key(self):
        if not self.ssn:
            res = True
        else:
            res = self.calculate_ssn_key(self.ssn_no_key) == int(self.ssn_key)
        if not res:
            raise ValidationError(gettext('party_ssn.msg_invalid_ssn_key'))

    def get_ssn(self, name):
        if not self.ssn:
            return ''
        size = utils.get_field_size(self, name)
        if size:
            if name == 'ssn_no_key':
                return self.ssn[0:size]
            elif name == 'ssn_key':
                return self.ssn[-size:]
        return ''

    @classmethod
    def set_ssn(cls, persons, name, value):
        for person in persons:
            if not person.ssn:
                continue
            size = utils.get_field_size(person, name)
            if name == 'ssn_no_key':
                person.ssn = value + person.ssn[size:SSN_LENGTH]
            elif name == 'ssn_key':
                person.ssn = person.ssn[0:SSN_LENGTH - size] + value
            cls.write([person], {'ssn': person.ssn})

    @fields.depends('ssn_key', 'ssn_no_key')
    def on_change_with_ssn(self, name=None):
        return (self.ssn_no_key or '') + (self.ssn_key or '')

    def get_func_key(self, name):
        if self.is_person and self.ssn:
            return self.ssn
        return super(Party, self).get_func_key(name)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        domain = super(Party, cls).search_func_key(name, clause)
        if '|' in clause[2]:
            return domain
        if domain[0] == 'OR':
            domain.append([('ssn',) + tuple(clause[1:])])
        return domain

    def get_gdpr_data(self):
        res = super(Party, self).get_gdpr_data()
        res[self._label_gdpr(self, 'ssn')] = coog_string.translate_value(
            self, 'ssn')
        return res

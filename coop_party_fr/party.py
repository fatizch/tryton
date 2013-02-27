#-*- coding:utf-8 -*-
import copy
import re

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.coop_utils import utils

SSN_LENGTH = 15


class FrenchParty():
    'French Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    ssn_no_key = fields.Function(fields.Char('SSN', size=13),
        'get_ssn', setter='set_ssn')
    ssn_key = fields.Function(fields.Char('SSN Key', size=2),
        'get_ssn', setter='set_ssn')

    @classmethod
    def __setup__(cls):
        super(FrenchParty, cls).__setup__()
        cls.ssn = copy.copy(cls.ssn)
        cls.ssn.size = 15
        if cls.ssn.on_change_with is None:
            cls.ssn.on_change_with = []
        cls.ssn.on_change_with += ['ssn_no_key', 'ssn_key']

        cls._constraints += [
            ('check_ssn', 'invalid_ssn'),
            ('check_ssn_key', 'invalid_ssn_key'),
            ('check_ssn_birth_date', 'invalid_ssn_birth_date'),
            ('check_ssn_gender', 'invalid_ssn_gender'),
            ]
        cls._error_messages.update(
            {
                'invalid_ssn': 'Invalid format for SSN',
                'invalid_ssn_key': 'Invalid SSN Key',
                'invalid_ssn_birth_date': 'Incompatible birth date and SSN',
                'invalid_ssn_gender': 'Incompatible gender and SSN',
            })
        #Do not display SIREN for person
        cls.siren = copy.copy(cls.siren)
        cls.siren.states = {'invisible': Bool(~Eval('is_company'))}

    @staticmethod
    def calculate_ssn_key(ssn_no_key):
        ssn_as_num = str(ssn_no_key).replace('2A', '19').replace('2B', '18')
        key = 97 - int(ssn_as_num) % 97
        return key

    def check_ssn(self):
        if not self.ssn:
            return True
        pattern = """^[1-3]
            [0-9]{2}
            [0-1][0-9]
            (2[AB]|[0-9]{2})
            [0-9]{3}
            [0-9]{3}
            [0-9]{2}$"""
        return re.search(pattern, self.ssn, re.X)

    def check_ssn_key(self):
        if not self.ssn:
            return True
        return self.calculate_ssn_key(self.ssn_no_key) == int(self.ssn_key)

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
            size = utils.get_field_size(person, name)
            if name == 'ssn_no_key':
                person.ssn = value + person.ssn[size:SSN_LENGTH]
            elif name == 'ssn_key':
                person.ssn = person.ssn[0:SSN_LENGTH - size] + value
            cls.write([person], {'ssn': person.ssn})

    def on_change_with_ssn(self, name=None):
        return self.ssn_no_key + self.ssn_key

    def check_ssn_birth_date(self):
        if not self.ssn:
            return True
        return self.birth_date.strftime('%y%m') == self.ssn[1:5]

    def check_ssn_gender(self):
        if not self.ssn or (self.ssn[0] != '1' and self.ssn[0] != '2'):
            return True
        return self.ssn[0] == str(self.get_gender_as_int())

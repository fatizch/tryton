#-*- coding:utf-8 -*-

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.modules.coop_utils import DynamicSelection, utils as utils
from trytond.modules.coop_utils import string as string

__all__ = ['Address', 'AddresseKind']


class Address(ModelSQL, ModelView):
    "Address"
    __name__ = 'party.address'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    kind = fields.Selection('get_possible_address_kind', 'Kind')

    def get_summary(self, name=None, at_date=None):
        res = ''
        indent = 0
        if self.kind:
            res = string.get_field_as_summary(self, 'kind', False, at_date)
            indent = 1
        res += string.re_indent_text(self.get_full_address(name), indent)
        return res

    @staticmethod
    def default_start_date():
        return utils.today()

    @staticmethod
    def get_possible_address_kind():
        return AddresseKind.get_values_as_selection('party.address_kind')

    @staticmethod
    def default_kind():
        'RSE TODO : what if this address kind was removed or modified?'
        return 'main'


class AddresseKind(DynamicSelection):
    'Addresse Kind'

    __name__ = 'party.address_kind'
    _table = 'coop_table_of_table'

    @staticmethod
    def get_class_where_used():
        return [('party.address', 'kind')]

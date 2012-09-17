#-*- coding:utf-8 -*-

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.modules.coop_utils import utils as utils

__all__ = ['Address']


class Address(ModelSQL, ModelView):
    "Address"
    __name__ = 'party.address'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    def get_summary(self, name=None, at_date=None):
        res = self.get_full_address(name)
        return res

    @staticmethod
    def default_start_date():
        return utils.today()

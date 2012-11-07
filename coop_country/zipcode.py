#-*- coding:utf-8 -*-
from trytond.model import ModelView, ModelSQL, fields as fields

__all__ = ['ZipCode']


class ZipCode(ModelSQL, ModelView):
    'ZipCode'

    __name__ = 'country.zipcode'

    zip = fields.Char('Zip', required=True, select=True)
    city = fields.Char('City', required=True)
    country = fields.Many2One('country.country', 'Country', required=True)

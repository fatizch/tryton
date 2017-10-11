# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model, fields

__all_ = [
    'HealthCareSystem',
    'InsuranceFund',
    ]


class HealthCareSystem(model.CoogSQL, model.CoogView):
    'Health Care System'

    __name__ = 'health.care_system'
    _order_name = 'code'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name')
    short_name = fields.Char('Short Name')

    @classmethod
    def search_rec_name(cls, name, clause):
        return [
            'OR',
            ('name',) + tuple(clause[1:]),
            ('code',) + tuple(clause[1:]),
        ]

    def get_rec_name(self, name):
        return '%s (%s)' % (self.name, self.code)


class InsuranceFund(model.CoogSQL, model.CoogView):
    'Insurance Fund'

    __name__ = 'health.insurance_fund'
    _func_key = 'code'
    code = fields.Char('Code')
    name = fields.Char('Name')
    department = fields.Char('Department')
    hc_system = fields.Many2One('health.care_system', 'Health Care System',
        ondelete='CASCADE')

    @classmethod
    def search_from_zipcode_and_hc_system(cls, zipcode, hc_system):
        if zipcode[0:2] in ['97', '98']:
            dep = zipcode[0:3]
        else:
            dep = zipcode[0:2]
        return cls.search([
                ('department', '=', dep),
                ('hc_system', '=', hc_system),
                ])

    @classmethod
    def search_rec_name(cls, name, clause):
        return [
            'OR',
            ('name',) + tuple(clause[1:]),
            ('code',) + tuple(clause[1:]),
        ]

    def get_rec_name(self, name):
        return '%s (%s)' % (self.name, self.code)

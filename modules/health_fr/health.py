from trytond.modules.coop_utils import model, fields

__all_ = [
    'HealthCareSystem',
    'InsuranceFund',
    ]


class HealthCareSystem(model.CoopSQL, model.CoopView):
    'Health Care System'

    __name__ = 'health.care_system'
    _order_name = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name')
    short_name = fields.Char('Short Name')


class InsuranceFund(model.CoopSQL, model.CoopView):
    'Insurance Fund'

    __name__ = 'health.insurance_fund'
    code = fields.Char('Code')
    name = fields.Char('Name')
    department = fields.Char('Department')
    regime = fields.Many2One('health.care_system', 'Health Care System')

    @classmethod
    def search_from_zipcode_and_regime(cls, zipcode, regime):
        if zipcode[0:2] in ['97', '98']:
            dep = zipcode[0:3]
        else:
            dep = zipcode[0:2]
        return cls.search([
                ('department', '=', dep),
                ('regime', '=', regime),
                ])

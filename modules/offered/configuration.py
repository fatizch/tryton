# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView, ModelSQL, ModelSingleton
__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Offered Configuration'
    __name__ = 'offered.configuration'

    @staticmethod
    def get_field(model_name, field_name):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        company_id = Transaction().context.get('company')
        field, = ModelField.search([
            ('model.model', '=', model_name),
            ('name', '=', field_name),
            ], limit=1)
        properties = Property.search([
            ('field', '=', field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ], limit=1)
        if properties:
            prop, = properties
            return prop.value.id

    @staticmethod
    def set_field(model_name, field_name, relation_model_name, value):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        company_id = Transaction().context.get('company')
        field, = ModelField.search([
            ('model.model', '=', model_name),
            ('name', '=', field_name),
            ], limit=1)
        properties = Property.search([
            ('field', '=', field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ])
        with Transaction().set_user(0):
            Property.delete(properties)
            if value:
                Property.create([{
                            'field': field.id,
                            'value': '%s,%s' % (relation_model_name, value),
                            'company': company_id,
                            }])

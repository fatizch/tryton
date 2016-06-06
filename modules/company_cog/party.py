from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = ['PartyConfiguration']


class PartyConfiguration:
    __name__ = 'party.configuration'

    def get_party_lang(self, name):
        pool = Pool()
        Property = pool.get('ir.property')
        company_id = Transaction().context.get('company')
        lang_field = self._get_lang_field(name)
        properties = Property.search([
                ('field', '=', lang_field.id),
                ('res', '=', None),
                ('company', '=', company_id),
                ], limit=1)
        if properties:
            prop, = properties
            return prop.value.id

    @classmethod
    def set_party_lang(cls, configurations, name, value):
        pool = Pool()
        Property = pool.get('ir.property')
        company_id = Transaction().context.get('company')
        lang_field = cls._get_lang_field(name)
        properties = Property.search([
                ('field', '=', lang_field.id),
                ('res', '=', None),
                ('company', '=', company_id),
                ])
        Property.delete(properties)
        if value:
            Property.create([{
                        'field': lang_field.id,
                        'value': 'ir.lang,%s' % value,
                        'company': company_id,
                        }])

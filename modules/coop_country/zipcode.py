#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.modules.coop_utils import coop_string, fields, model, export

__all__ = [
    'Country',
    'ZipCode',
]


export.add_export_to_model([
    ('country.subdivision', ('code',)),
])


class Country(export.ExportImportMixin):
    'Country'

    __metaclass__ = PoolMeta
    __name__ = 'country.country'

    @classmethod
    def _export_keys(cls):
        return set(['code'])

    @classmethod
    def _export_force_recreate(cls):
        result = super(Country, cls)._export_force_recreate()
        result.remove('subdivisions')
        return result


class ZipCode(model.CoopSQL, model.CoopView):
    'ZipCode'

    __name__ = 'country.zipcode'
    _rec_name = 'zip'

    zip = fields.Char('Zip', required=True, select=True)
    city = fields.Char('City', required=True, select=True)
    country = fields.Many2One('country.country', 'Country', required=True)

    def get_rec_name(self, name=None):
        return '%s %s' % (self.zip, self.city)

    @staticmethod
    def replace_city_name_with_support_for_french_sna(city):
        #French zip code are validated by SNA
        #http://www.laposte.fr/sna/rubrique.php3?id_rubrique=59
        #and some modification must be made on city name to be validated
        #remove accentued char
        city = coop_string.remove_invalid_char(city)
        #remove apostrophe
        city = city.replace('\'', ' ').replace('-', ' ').upper()
        #remove all other ponctuation
        city = coop_string.remove_all_but_alphanumeric_and_space(city)
        if city.startswith('SAINT '):
            city = 'ST ' + city[6:]
        if city.startswith('SAINTE '):
            city = 'STE ' + city[7:]
        city = city.replace(' SAINT ', ' ST ')
        city = city.replace(' SAINTE ', ' STE ')
        return city

    @classmethod
    def search_rec_name(cls, name, clause):
        domain = [(
            'city', clause[1],
            cls.replace_city_name_with_support_for_french_sna(clause[2]))]
        if cls.search(domain, limit=1):
            return domain
        return [(cls._rec_name,) + clause[1:]]

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        res = super(ZipCode, cls).search(
            domain, offset, limit, order, count, query_string)
        if res:
            return res
        for cur_domain in domain:
            if cur_domain and cur_domain[0] == 'city':
                city = cls.replace_city_name_with_support_for_french_sna(
                    cur_domain[2])
                domain.remove(cur_domain)
                if 'like' in cur_domain[1]:
                    city = '%' + city + '%'
                domain.append([u'city', cur_domain[1], city])
                break
        return super(ZipCode, cls).search(
            domain, offset, limit, order, count, query_string)

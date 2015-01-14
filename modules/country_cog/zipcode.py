# -*- coding:utf-8 -*-
import re
from trytond.modules.cog_utils import coop_string, fields, model


__all__ = [
    'ZipCode',
    ]


class ZipCode(model.CoopSQL, model.CoopView):
    'ZipCode'

    __name__ = 'country.zipcode'
    _rec_name = 'zip'

    zip = fields.Char('Zip', required=True, select=True)
    city = fields.Char('City', required=True, select=True)
    country = fields.Many2One('country.country', 'Country', required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(ZipCode, cls).__setup__()
        cls._order.insert(0, ('country', 'ASC'))
        cls._order.insert(1, ('zip', 'ASC'))
        cls._order.insert(2, ('city', 'ASC'))
        cls._sql_constraints += [
            ('zip_uniq', 'UNIQUE(zip, city, country)',
                'This city and this zipcode already exist for this country!'),
            ]

    def get_rec_name(self, name=None):
        return '%s %s' % (self.zip, self.city)

    @staticmethod
    def replace_city_name_with_support_for_french_sna(city):
        # French zip code are validated by SNA
        # and some modification must be made on city name to be validated
        city = coop_string.slugify(city, ' ', lower=False).upper().\
            replace('-', ' ').strip()
        city = re.compile(r'([^\s\w]|_)+').sub('', city)  # remove ponctuations
        regex = r'(?P<before>(.* )?)SAINT(?P<e>E?) (?P<after>.*)'
        m = re.match(regex, city)
        return u'%sST%s %s' % (m.group('before'), m.group('e'),
            m.group('after')) if m else city

    @classmethod
    def search_rec_name(cls, name, clause):
        domain = [(
            'city', clause[1],
            cls.replace_city_name_with_support_for_french_sna(
                unicode(clause[2])))]
        if cls.search(domain, limit=1):
            return domain
        return [(cls._rec_name,) + tuple(clause[1:])]

    @classmethod
    def _export_light(cls):
        return set(['country'])

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        res = super(ZipCode, cls).search(
            domain, offset, limit, order, count, query)
        if res:
            return res
        for cur_domain in domain:
            if cur_domain and cur_domain[0] == 'city':
                city = cls.replace_city_name_with_support_for_french_sna(
                    cur_domain[2])
                domain.remove(cur_domain)
                if 'like' in cur_domain[1]:
                    city = u'%' + city + u'%'
                domain.append([u'city', cur_domain[1], city])
                break
        return super(ZipCode, cls).search(
            domain, offset, limit, order, count, query)

    @fields.depends('city', 'country')
    def on_change_with_city(self):
        if not self.country or self.country.code != 'FR':
            return self.city
        return self.replace_city_name_with_support_for_french_sna(self.city)

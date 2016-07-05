# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond import backend

from trytond.modules.cog_utils import coop_string, fields

__metaclass__ = PoolMeta
__all__ = [
    'Zip',
    ]


class Zip:
    __name__ = 'country.zip'

    line5 = fields.Char('Line 5', select=True)

    @classmethod
    def __setup__(cls):
        super(Zip, cls).__setup__()
        cls._order.insert(3, ('line5', 'ASC'))
        t = cls.__table__()
        cls._sql_constraints = [x for x in cls._sql_constraints if x[0]
            is not 'zip_uniq']
        cls._sql_constraints += [
            ('zip_uniq_all', Unique(t, t.zip, t.city, t.line5, t.country),
                'This city, zipcode, line5 combination already exists'
                ' for this country!'),
            ]

    @classmethod
    def __register__(cls, module_name):
        super(Zip, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        TableHandler(cls, module_name).drop_constraint(
            'zip_uniq')

    @classmethod
    def default_line5(cls):
        return ''

    def get_rec_name(self, name=None):
        base = super(Zip, self).get_rec_name(None)
        if not self.line5:
            return base
        return base + ' ' + self.line5

    @staticmethod
    def replace_city_name_with_support_for_french_sna(city):
        # French zip code are validated by SNA
        # and some modification must be made on city name to be validated
        city = coop_string.slugify(city, ' ', lower=False).upper().\
            replace('-', ' ').strip()
        city = re.compile(r'([^\s\w]|_)+').sub('', city)  # remove ponctuations
        regex = r'(?P<before>(.* )?)SAINT(?P<e_letter>E?) (?P<after>.*)'

        def replace(city):
            m = re.match(regex, city)
            if m:
                city = u'%sST%s %s' % (m.group('before'), m.group('e_letter'),
                    m.group('after'))
                return replace(city)
            return city

        city = replace(city)
        return city

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
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        res = super(Zip, cls).search(
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
        return super(Zip, cls).search(
            domain, offset, limit, order, count, query)

    @fields.depends('city', 'country')
    def on_change_with_city(self):
        if not self.country or self.country.code != 'FR':
            return self.city
        return self.replace_city_name_with_support_for_french_sna(self.city)

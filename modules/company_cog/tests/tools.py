# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from trytond.modules.company.tests import tools


def create_company(*args, **kwargs):
    Party = Model.get('party.party')
    Country = Model.get('country.country')

    if 'party' not in kwargs:
        kwargs['party'] = p = Party(name='Dunder Mifflin')
        a = p.all_addresses[0]
        a.street = 'Adresse Inconnue'
        a.zip = '99999'
        a.city = 'Bioul'
        a.country, = Country.find([('code', '=', 'FR')]) or [None]
        p.save()

    res_conf = tools.create_company(*args, **kwargs)
    company = tools.get_company(kwargs.get('config', None))
    if not company.party.lang:
        company.party.lang, = Model.get('ir.lang').find(
            [('code', '=', 'en')])
        company.party.save()
    return res_conf

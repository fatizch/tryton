# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If

from trytond.modules.coog_core import model, coog_string
from trytond.modules.offered.extra_data import with_extra_data


_all_ = [
    'Party',
    ]


class Party(with_extra_data(['party_person', 'party_company',
        'covered_element']), metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.extra_data.domain = [If(Bool(Eval('is_person')),
            ['OR',
                [('kind', '=', 'party_person')],
                [('kind', '=', 'covered_element'),
                    ('store_on_party', '=', True)]],
            [('kind', '=', 'party_company')])]
        cls.extra_data.depends += ['is_person']

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [(
                '/form/group[@id="party_extra_data"]',
                'states',
                {'invisible': ~Bool(Eval('extra_data', None))}
                )]

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        cls.check_extra_data(parties)

    @classmethod
    def default_extra_data(cls):
        return {}

    @classmethod
    def check_extra_data(cls, parties):
        ExtraData = Pool().get('extra_data')
        with model.error_manager():
            for party in parties:
                ExtraData.check_extra_data(party, 'extra_data')

    def get_gdpr_data(self):
        res = super(Party, self).get_gdpr_data()
        ExtraData = Pool().get('extra_data')
        value_ = coog_string.translate_value
        extras = ExtraData.search([
                ('name', 'in', list(self.extra_data.keys())),
                ('gdpr', '=', True)])
        res.update({value_(extra, 'rec_name'): self.extra_data[extra.name]
                for extra in extras})
        return res

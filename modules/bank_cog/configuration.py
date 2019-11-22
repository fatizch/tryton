# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import model, fields


__all__ = [
    'Configuration',
    'SwiftPartyConfiguration',
    ]


class Configuration(metaclass=PoolMeta):
    __name__ = 'party.configuration'

    bic_swift_countries = fields.Many2Many(
        'country.country-swift-party.configuration', 'configuration', 'country',
        'BIC swift countries', help='Countries used to import swift bic')


class SwiftPartyConfiguration(model.CoogSQL, model.CoogView):
    'Country Party Configuration'

    __name__ = 'country.country-swift-party.configuration'

    configuration = fields.Many2One('party.configuration', 'Configuration',
        required=True, ondelete='RESTRICT')
    country = fields.Many2One('country.country', 'Country', ondelete='RESTRICT',
        required=True)

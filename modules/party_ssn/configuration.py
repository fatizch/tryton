# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


__all__ = [
    'Configuration',
    ]


class Configuration(metaclass=PoolMeta):
    __name__ = 'party.configuration'

    check_ssn_with_party_information = fields.Boolean(
        'Check ssn with party information',
        help='If check, SSN will be validated based on gender,'
             ' birth date and birth zip code information')

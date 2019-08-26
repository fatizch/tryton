# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.pool import PoolMeta


__all__ = [
    'ImportProcessSelect',
    ]


class ImportProcessSelect(metaclass=PoolMeta):
    __name__ = 'import.process.select'

    def available_processes(self):
        return super(ImportProcessSelect, self).available_processes() + [
            {
                'name': gettext(
                    'underwriting_process.msg_underwriting_std_process'),
                'path':
                'underwriting_process/json/process_underwriting_standard_fr'
                '.json',
                'description': gettext(
                    'underwriting_process'
                    '.msg_underwriting_std_process_description'),
                'is_visible': True,
                },
            ]

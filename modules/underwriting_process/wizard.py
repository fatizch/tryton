# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


__all__ = [
    'ImportProcessSelect',
    ]


class ImportProcessSelect:
    __metaclass__ = PoolMeta
    __name__ = 'import.process.select'

    @classmethod
    def __setup__(cls):
        super(ImportProcessSelect, cls).__setup__()
        cls._error_messages.update({
                'underwriting_std_process': 'Underwriting Process (FR)',
                'underwriting_std_process_description': 'This process allows '
                'managers to request an underwriting',
                })

    def available_processes(self):
        return super(ImportProcessSelect, self).available_processes() + [
            {
                'name': self.raise_user_error(
                    'underwriting_std_process', raise_exception=False),
                'path':
                'underwriting_process/json/process_underwriting_standard_fr'
                '.json',
                'description': self.raise_user_error(
                    'underwriting_std_process_description',
                    raise_exception=False),
                'is_visible': True,
                },
            ]

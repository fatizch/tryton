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
                'life_process': 'Life Process',
                'life_process_description': 'This process allows managers to '
                'launch a life insurance subscribtion process depending on a '
                'product',
                })

    def available_processes(self):
        return super(ImportProcessSelect, self).available_processes() + [
            {
                'name': self.raise_user_error(
                    'life_process', raise_exception=False),
                'path':
                'contract_insurance_process/json/process_life_subscription.'
                'json',
                'description': self.raise_user_error(
                    'life_process_description', raise_exception=False),
                },
            ]

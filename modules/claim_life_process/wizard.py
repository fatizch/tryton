# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import utils

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
                'std_declaration_process': 'STD Declaration Process (FR)',
                'std_declaration_process_description': 'This process allows '
                'managers to make a STD declaration',
                'ltd_declaration_process': 'LTD Declaration Process (FR)',
                'ltd_declaration_process_description': 'This process allows '
                'managers to make a LTD declaration',
                })

    def available_processes(self):
        return super(ImportProcessSelect, self).available_processes() + [
            {
                'name': self.raise_user_error(
                    'std_declaration_process', raise_exception=False),
                'path':
                'claim_life_process/json/process_std_declaration_fr.json',
                'description': self.raise_user_error(
                    'std_declaration_process_description',
                    raise_exception=False),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility'),
                },
            {
                'name': self.raise_user_error(
                    'ltd_declaration_process', raise_exception=False),
                'path':
                'claim_life_process/json/process_ltd_declaration_fr.json',
                'description': self.raise_user_error(
                    'ltd_declaration_process_description',
                    raise_exception=False),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility'),
                },
            ]

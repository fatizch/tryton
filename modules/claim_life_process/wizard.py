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
                'relapse_declaration_process': 'Relapse Declaration Process '
                '(FR)',
                'relapse_declaration_process_description': 'This process '
                'allows managers to make a relapse declaration',
                'death_declaration_process': 'Death Declaration Process '
                '(FR)',
                'death_declaration_process_description': 'This process '
                'allows managers to make a death declaration',
                'ltd_declaration_process': 'LTD Declaration Process (FR)',
                'ltd_declaration_process_description': 'This process allows '
                'managers to make a LTD declaration',
                'death_std_declaration_process': 'STD/Death Declaration '
                'Process (FR)',
                'death_std_declaration_process_description': 'This process '
                'allows managers to reopen a std claim to make a death '
                'declaration',
                'std_continue_new_period_process': 'STD Continue/New Period '
                'Process (FR)',
                'std_continue_new_period_process_description': 'This process '
                'allows managers to continue a terminated STD declaration and '
                'add new scheduling periods',
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
            {
                'name': self.raise_user_error(
                    'relapse_declaration_process', raise_exception=False),
                'path':
                'claim_life_process/json/process_relapse_declaration_fr.json',
                'description': self.raise_user_error(
                    'relapse_declaration_process_description',
                    raise_exception=False),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility')
            },
            {
                'name': self.raise_user_error(
                    'death_declaration_process', raise_exception=False),
                'path':
                'claim_life_process/json/process_deces_declaration_fr.json',
                'description': self.raise_user_error(
                    'death_declaration_process_description',
                    raise_exception=False),
                'is_visible': utils.is_module_installed('claim_eckert') and
                utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility')
                },
            {
                'name': self.raise_user_error(
                    'death_std_declaration_process', raise_exception=False),
                'path':
                'claim_life_process/json/process_deces_suite_std_declaration_'
                'fr.json',
                'description': self.raise_user_error(
                    'death_std_declaration_process_description',
                    raise_exception=False),
                'is_visible': utils.is_module_installed('claim_eckert') and
                utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility')
                },
            {
                'name': self.raise_user_error(
                    'std_continue_new_period_process', raise_exception=False),
                'path':
                'claim_life_process/json/process_std_continue_new_period_fr.'
                'json',
                'description': self.raise_user_error(
                    'std_continue_new_period_process_description',
                    raise_exception=False),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility'),
                }
            ]

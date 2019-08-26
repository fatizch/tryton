# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta

from trytond.modules.coog_core import utils

__all__ = [
    'ImportProcessSelect',
    ]


class ImportProcessSelect(metaclass=PoolMeta):
    __name__ = 'import.process.select'

    def available_processes(self):
        return super(ImportProcessSelect, self).available_processes() + [
            {
                'name': gettext(
                    'claim_life_process.msg_std_declaration_process'),
                'path':
                'claim_life_process/json/process_std_declaration_fr.json',
                'description': gettext(
                    'claim_life_process'
                    '.msg_std_declaration_process_description'),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility'),
                },
            {
                'name': gettext(
                    'claim_life_process.msg_ltd_declaration_process'),
                'path':
                'claim_life_process/json/process_ltd_declaration_fr.json',
                'description': gettext(
                    'claim_life_process'
                    '.msg_ltd_declaration_process_description'),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility'),
                },
            {
                'name': gettext(
                    'claim_life_process.msg_relapse_declaration_process'),
                'path':
                'claim_life_process/json/process_relapse_declaration_fr.json',
                'description': gettext(
                    'claim_life_process'
                    '.msg_relapse_declaration_process_description'),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility')
            },
            {
                'name': gettext(
                    'claim_group_process.msg_death_declaration_process'),
                'path':
                'claim_life_process/json/process_deces_declaration_fr.json',
                'description': gettext(
                    'claim_life_process'
                    '.msg_death_declaration_process_description'),
                'is_visible': utils.is_module_installed('claim_eckert') and
                utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility')
                },
            {
                'name': gettext(
                    'claim_life_process.msg_death_std_declaration_process'),
                'path':
                'claim_life_process/json/process_deces_suite_std_declaration_'
                'fr.json',
                'description': gettext(
                    'claim_life_process'
                    '.msg_death_std_declaration_process_description'),
                'is_visible': utils.is_module_installed('claim_eckert') and
                utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility')
                },
            {
                'name': gettext(
                    'claim_life_process.msg_std_continue_new_period_process'),
                'path':
                'claim_life_process/json/process_std_continue_new_period_fr.'
                'json',
                'description': gettext(
                    'claim_life_process'
                    '.msg_std_continue_new_period_process_description'),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility'),
                },
            {
                'name': gettext(
                    'claim_life_process.msg_ltd_after_std_process'),
                'path':
                'claim_life_process/json/process_ltd_after_std_declaration_fr.'
                'json',
                'description': gettext(
                    'claim_life_process.msg_ltd_after_std_process_description'),
                'is_visible': utils.is_module_installed('claim_salary_fr') and
                utils.is_module_installed('claim_group_process') and
                utils.is_module_installed('underwriting_claim') and
                utils.is_module_installed('process_rule') and
                utils.is_module_installed('claim_eligibility'),
                },
            ]

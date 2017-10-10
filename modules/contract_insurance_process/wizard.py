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
                'standard_process': 'Standard Insurance Subscription Process '
                '(FR)',
                'standard_process_description': 'This process allows managers '
                'to launch a standard insurance subscription process '
                'depending on a product',
                'loan_process': 'Loan Process (FR)',
                'loan_process_description': 'This process allows managers to '
                'launch a loan insurance subscription process '
                'depending on a product',
                })

    def available_processes(self):
        return super(ImportProcessSelect, self).available_processes() + [
            {
                'name': self.raise_user_error(
                    'standard_process', raise_exception=False),
                'path':
                'contract_insurance_process/json/process_standard_subscription'
                '_fr.json',
                'description': self.raise_user_error(
                    'standard_process_description', raise_exception=False),
                'is_visible':
                utils.is_module_installed('contract_insurance_invoice') and
                utils.is_module_installed('contract_insurance_process')
                },
            {
                'name': self.raise_user_error(
                    'loan_process', raise_exception=False),
                'path':
                'contract_insurance_process/json/process_loan_subscription_fr'
                '.json',
                'description': self.raise_user_error(
                    'loan_process_description', raise_exception=False),
                'is_visible':
                utils.is_module_installed('contract_loan_invoice') and
                utils.is_module_installed('contract_insurance_process')
                },
            ]

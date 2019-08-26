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
                'name': gettext('contract_process.msg_standard_process'),
                'path':
                'contract_process/json/process_standard_subscription'
                '_fr.json',
                'description': gettext(
                    'contract_process.msg_standard_process_description'),
                'is_visible':
                utils.is_module_installed('contract_insurance_invoice') and
                utils.is_module_installed('contract_process')
                },
            {
                'name': gettext('contract_process.msg_loan_process'),
                'path':
                'contract_process/json/process_loan_subscription_fr'
                '.json',
                'description': gettext(
                    'contract_process.msg_loan_process_description'),
                'is_visible':
                utils.is_module_installed('contract_loan_invoice') and
                utils.is_module_installed('contract_process')
                },
            ]

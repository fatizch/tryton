# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model

__all__ = [
    'Configuration',
    'ConfigurationTerminationReason',
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'offered.configuration'

    remove_commission_for_sub_status = fields.Many2Many(
        'offered.configuration-contract.sub_status', 'configuration',
        'sub_status', 'Termination Sub Status That Remove Unpaid Prepayment',
        domain=[('status', '=', 'terminated')])


class ConfigurationTerminationReason(model.CoogSQL):
    'Configuration to Termination Reason'

    __name__ = 'offered.configuration-contract.sub_status'

    configuration = fields.Many2One('offered.configuration', 'Configuration',
        ondelete='CASCADE', required=True, select=True)
    sub_status = fields.Many2One('contract.sub_status', 'Sub Status',
        ondelete='RESTRICT', required=True)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'offered.configuration'

    inactivity_delay = fields.Integer('Inactivity Delay',
            states={
                'required': Bool(Eval('automatic_decline_reason')),
                }, depends=['automatic_decline_reason'],
        help='All quotes inactive since stricly more than this period '
        '(in days) will be declined.')
    delay_unit = fields.Selection([
            ('month', 'Months'),
            ('day', 'Days')
            ], 'Delay Unit')
    automatic_decline_reason = fields.Many2One('contract.sub_status',
        'Automatic Decline Reason', states={
            'required': Bool(Eval('inactivity_delay')),
            }, depends=['inactivity_delay'],
            ondelete='RESTRICT')

    @staticmethod
    def default_delay_unit():
        return 'day'

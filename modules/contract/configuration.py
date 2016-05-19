from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'offered.configuration'

    default_quote_number_sequence = fields.Function(fields.Many2One(
        'ir.sequence', 'Default quote number sequence',
        domain=[
                ('code', '=', 'quote'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]),
        'get_sequence', setter='set_sequence')
    inactivity_delay = fields.Integer('Inactivity Delay',
            states={
                'required': Bool(Eval('automatic_decline_reason')),
                }, depends=['automatic_decline_reason'],
        help='All quotes inactive since stricly more than this period '
        '(in days) will be declined.')
    automatic_decline_reason = fields.Many2One('contract.sub_status',
        'Automatic Decline Reason', states={
            'required': Bool(Eval('inactivity_delay')),
            }, depends=['inactivity_delay'],
            ondelete='RESTRICT')

    def get_sequence(self, name):
        return self.get_field('offered.product', name[8:])

    @classmethod
    def set_sequence(cls, configurations, name, value):
        return cls.set_field('offered.product', name[8:], 'ir.sequence', value)

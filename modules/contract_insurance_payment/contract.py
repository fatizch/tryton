from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    processing_payments = fields.Function(
        fields.Many2Many('account.payment', None, None, 'Processing Payments'),
        'get_payments_by_state')
    succeeded_payments = fields.Function(
        fields.Many2Many('account.payment', None, None, 'Succeeded Payments'),
        'get_payments_by_state')
    failed_payments = fields.Function(
        fields.Many2Many('account.payment', None, None, 'Failed Payments'),
        'get_payments_by_state')

    def get_payments_by_state(self, name):
        pool = Pool()
        state = name.split('_')[0]
        Payment = pool.get('account.payment')
        return [x.id for x in Payment.search([('line.contract', '=', self),
            ('state', '=', state)])]

from trytond.pool import PoolMeta, Pool
from trytond.model import fields

__all__ = ['Move', 'MoveLine', 'Account']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'account.move'

    billing_period = fields.Many2One('billing.period', 'Billing Period',
        ondelete='RESTRICT')

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['contract.contract']


class MoveLine:
    __name__ = 'account.move.line'

    second_origin = fields.Reference('Second Origin',
        selection='get_second_origin')
    origin_name = fields.Function(fields.Char('Origin Name'),
        'get_origin_name')

    def get_origin_name(self, name):
        if not (hasattr(self, 'origin') and self.origin):
            return ''
        return self.origin.rec_name

    @classmethod
    def _get_second_origin(cls):
        return [
            'offered.product',
            'offered.coverage',
            ]

    @classmethod
    def get_second_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_second_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]


class Account:
    __name__ = 'account.account'

    @classmethod
    def _export_skips(cls):
        res = super(Account, cls)._export_skips()
        res.add('left')
        res.add('right')
        return res

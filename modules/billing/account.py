from trytond.pool import PoolMeta, Pool
from trytond.model import fields

__all__ = ['Move', 'MoveLine']
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

    second_origin = fields.Reference('Second Origin', selection='get_origin')

    @classmethod
    def _get_origin(cls):
        return [
            'ins_product.product',
            'ins_product.coverage',
            ]

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

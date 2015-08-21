from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product'
    ]


class Product:
    __name__ = 'offered.product'

    dunning_procedure = fields.Many2One('account.dunning.procedure',
        'Dunning Procedure', ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'dunning_procedure'}

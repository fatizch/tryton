from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'ExportPackage',
    ]


class ExportPackage:
    __name__ = 'ir.export_package'

    com_products = fields.Function(
        fields.One2Many('distribution.commercial_product', None,
            'Com Products', states={'invisible':
                    Bool(Eval('model') != 'distribution.commercial_product')},
                on_change=['com_products', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('distribution.commercial_product', 'Commercial Product'),
                ])
        return list(set(res))

    def on_change_com_products(self):
        return self._on_change('com_products')

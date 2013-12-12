from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'ExportPackage',
    ]


class ExportPackage():
    'Export Package'

    __name__ = 'ir.export_package'

    products = fields.Function(
        fields.One2Many('offered.product', None, 'Products', states={
                'invisible': Bool(Eval('model') != 'offered.product')},
                on_change=['products', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')
    coverages = fields.Function(
        fields.One2Many('offered.option.description', None, 'Coverages', states={
                'invisible': Bool(Eval('model') != 'offered.option.description')},
                on_change=['coverages', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')
    compl_data_defs = fields.Function(
        fields.One2Many('extra_data', None,
            'Complementary Data Def', states={
                'invisible': Bool(Eval('model') != 'extra_data')},
                on_change=['compl_data_defs', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('offered.product', 'Product'),
                ('offered.option.description', 'Coverage'),
                ('extra_data', 'Complementary Data'),
                ])
        return list(set(res))

    def on_change_products(self):
        return self._on_change('products')

    def on_change_coverages(self):
        return self._on_change('coverages')

    def on_change_compl_data_defs(self):
        return self._on_change('compl_data_defs')

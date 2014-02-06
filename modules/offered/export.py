from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields

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
                add_remove=[]),
        'getter_void', setter='setter_void')
    coverages = fields.Function(
        fields.One2Many('offered.option.description', None,
            'OptionDescriptions', states={
                'invisible':
                Bool(Eval('model') != 'offered.option.description')},
            add_remove=[]),
        'getter_void', setter='setter_void')
    extra_data_defs = fields.Function(
        fields.One2Many('extra_data', None,
            'Extra Data Def', states={
                'invisible': Bool(Eval('model') != 'extra_data')},
                add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('offered.product', 'Product'),
                ('offered.option.description', 'OptionDescription'),
                ('extra_data', 'Extra Data'),
                ])
        return list(set(res))

    @fields.depends('products', 'instances_to_export')
    def on_change_products(self):
        return self._on_change('products')

    @fields.depends('coverages', 'instances_to_export')
    def on_change_coverages(self):
        return self._on_change('coverages')

    @fields.depends('extra_data_defs', 'instances_to_export')
    def on_change_extra_data_defs(self):
        return self._on_change('extra_data_defs')

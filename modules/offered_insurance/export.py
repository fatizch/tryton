from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'ExportPackage',
    ]


class ExportPackage:
    __name__ = 'ir.export_package'

    exclusions = fields.Function(
        fields.One2Many('offered.exclusion', None, 'Exclusion', states={
                'invisible': Bool(Eval('model') != 'offered.exclusion')},
                on_change=['exclusions', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('offered.exclusion', 'Exclusion'),
                ])
        return list(set(res))

    def on_change_exclusions(self):
        return self._on_change('exclusions')

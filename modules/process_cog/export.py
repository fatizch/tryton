from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'ExportPackage',
    ]


class ExportPackage:
    __name__ = 'ir.export_package'

    process = fields.Function(
        fields.One2Many('process', None, 'Process', states={
                'invisible': Bool(Eval('model') != 'process')},
                add_remove=[]),
        'getter_void', setter='setter_void')
    steps = fields.Function(
        fields.One2Many('process.step', None, 'Steps', states={
                'invisible': Bool(Eval('model') != 'process.step')},
                add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('process', 'Process'),
                ('process.step', 'Steps'),
                ])
        return list(set(res))

    @fields.depends('process', 'instances_to_export')
    def on_change_process(self):
        return self._on_change('process')

    @fields.depends('steps', 'instances_to_export')
    def on_change_steps(self):
        return self._on_change('steps')

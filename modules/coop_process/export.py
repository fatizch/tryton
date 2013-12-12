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

    process = fields.Function(
        fields.One2Many('process.process_desc', None, 'Process', states={
                'invisible': Bool(Eval('model') != 'process.process_desc')},
                on_change=['process', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')
    steps = fields.Function(
        fields.One2Many('process.step_desc', None, 'Steps', states={
                'invisible': Bool(Eval('model') != 'process.step_desc')},
                on_change=['steps', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('process.process_desc', 'Process'),
                ('process.step_desc', 'Steps'),
                ])
        return list(set(res))

    def on_change_process(self):
        return self._on_change('process')

    def on_change_steps(self):
        return self._on_change('steps')

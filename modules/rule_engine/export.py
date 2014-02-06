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

    rules = fields.Function(
        fields.One2Many('rule_engine', None, 'Rules', states={
                'invisible': Bool(Eval('model') != 'rule_engine')},
            add_remove=[]),
        'getter_void', setter='setter_void')
    contexts = fields.Function(
        fields.One2Many('rule_engine.context', None, 'Contexts', states={
                'invisible': Bool(Eval('model') != 'rule_engine.context')},
            add_remove=[]),
        'getter_void', setter='setter_void')
    tree_elements = fields.Function(
        fields.One2Many('rule_engine.function', None,
            'Rule Functions', states={
                'invisible': Bool(Eval('model') != 'rule_engine.function')},
            add_remove=[]),
        'getter_void', setter='setter_void')
    tags = fields.Function(
        fields.One2Many('tag', None, 'Tags', states={
                'invisible': Bool(Eval('model') != 'tag')},
            add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('rule_engine', 'Rule'),
                ('rule_engine.context', 'Context'),
                ('rule_engine.function', 'Rule Function'),
                ('tag', 'Tag'),
                ])
        return list(set(res))

    @fields.depends('rules', 'instances_to_export')
    def on_change_rules(self):
        return self._on_change('rules')

    @fields.depends('contexts', 'instances_to_export')
    def on_change_contexts(self):
        return self._on_change('contexts')

    @fields.depends('tree_elements', 'instances_to_export')
    def on_change_tree_elements(self):
        return self._on_change('tree_elements')

    @fields.depends('tags', 'instances_to_export')
    def on_change_tags(self):
        return self._on_change('tags')

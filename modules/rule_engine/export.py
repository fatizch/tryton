from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'ExportPackage',
    ]


class ExportPackage():
    'Export Package'

    __name__ = 'coop_utils.export_package'

    rules = fields.Function(
        fields.One2Many('rule_engine', None, 'Rules', states={
                'invisible': Bool(Eval('model') != 'rule_engine')},
                on_change=['rules', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')
    contexts = fields.Function(
        fields.One2Many('rule_engine.context', None, 'Contexts', states={
                'invisible': Bool(Eval('model') != 'rule_engine.context')},
                on_change=['contexts', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')
    tree_elements = fields.Function(
        fields.One2Many('rule_engine.tree_element', None,
            'Tree Elements', states={
                'invisible': Bool(Eval('model') != 'rule_engine.tree_element')},
                on_change=['tree_elements', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')
    tags = fields.Function(
        fields.One2Many('tag', None, 'Tags', states={
                'invisible': Bool(Eval('model') != 'tag')},
                on_change=['tags', 'instances_to_export'],
                add_remove=[]),
        'getter_void', setter='setter_void')

    @classmethod
    def get_possible_models_to_export(cls):
        res = super(ExportPackage, cls).get_possible_models_to_export()
        res.extend([
                ('rule_engine', 'Rule'),
                ('rule_engine.context', 'Context'),
                ('rule_engine.tree_element', 'Tree Element'),
                ('tag', 'Tag'),
                ])
        return list(set(res))

    def on_change_rules(self):
        return self._on_change('rules')

    def on_change_contexts(self):
        return self._on_change('contexts')

    def on_change_tree_elements(self):
        return self._on_change('tree_elements')

    def on_change_tags(self):
        return self._on_change('tags')

import functools

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, Button
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['Rule', 'Context', 'TreeElement', 'ContextTreeElement', 'TestRule',
    'TestRuleStart', 'TestRuleTest']

CODE_TEMPLATE = """
def %s():
%%s

%s_result = %s()
"""


class Rule(ModelView, ModelSQL):
    "Rule"
    __name__ = 'rule_engine'

    name = fields.Char('Name', required=True)
    context = fields.Many2One('rule_engine.context', 'Context', required=True)
    code = fields.Text('Code')
    data_tree = fields.Function(fields.Text('Data Tree'), 'get_data_tree')

    def compute(self, evaluation_context):
        context = self.context.get_context()
        context.update(evaluation_context)
        context['context'] = context
        localcontext = {}
        code = '\n'.join(' ' + l for l in self.code.splitlines())
        code_template = CODE_TEMPLATE % (self.name, self.name, self.name)
        exec code_template % code in context, localcontext
        return localcontext['%s_result' % self.name]

    def data_tree(self, name):
        return ''


class Context(ModelView, ModelSQL):
    "Context"
    __name__ = 'rule_engine.context'

    name = fields.Char('Name', required=True)
    allowed_elements = fields.Many2Many(
        'rule_engine.context-rule_engine.tree_element', 'context',
        'tree_element', 'Allowed tree elements')

    def get_context(self):
        pool = Pool()
        context = {}
        for element in self.allowed_elements:
            namespace_obj = pool.get(element.namespace)
            context[element.name] = functools.partial(getattr(namespace_obj,
                    element.name), context)
        return context


class TreeElement(ModelView, ModelSQL):
    "Rule Engine Tree Element"
    __name__ = 'rule_engine.tree_element'

    name = fields.Char('Name', required=True)
    description = fields.Char('Description', translate=True)
    namespace = fields.Char('Namespace', required=True)
    parent = fields.Many2One('rule_engine.tree_element', 'Parent')
    children = fields.One2Many('rule_engine.tree_element', 'parent',
        'Children')


class ContextTreeElement(ModelSQL):
    "Context Tree Element"
    __name__ = 'rule_engine.context-rule_engine.tree_element'

    context = fields.Many2One('rule_engine.context', 'Context', required=True,
        ondelete='CASCADE')
    tree_element = fields.Many2One('rule_engine.tree_element', 'Tree Element',
        required=True, ondelete='CASCADE')


class TestRuleStart(ModelView):
    "Test Rule Input Form"
    __name__ = 'rule_engine.test_rule.start'

    context = fields.Text('Context')


class TestRuleTest(ModelView):
    "Test Rule Result Form"
    __name__ = 'rule_engine.test_rule.test'

    result = fields.Text('Result')


class TestRule(Wizard):
    "Test Rule Wizard"
    __name__ = 'rule_engine.test_rule'

    start = StateView('rule_engine.test_rule.start',
        'rule_engine.test_rule_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Test', 'test', 'tryton-go-next', True)
            ])
    test = StateView('rule_engine.test_rule.test',
        'rule_engine.test_rule_test_form', [
            Button('OK', 'end', 'tryton-ok', True),
            ])

    def default_start(self, fields):
        return {}

    def default_test(self, fields):
        Rule = Pool().get('rule_engine')

        context = eval(self.start.context)
        rule = Rule(Transaction().context['active_id'])
        return {
            'result': str(rule.compute(context)),
            }


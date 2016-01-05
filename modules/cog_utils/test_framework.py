import functools
import os
import imp

from trytond.transaction import Transaction
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT, ModuleTestCase


__all__ = [
    'get_module_test_case',
    'launch_function',
    'test_values_against_model',
    'prepare_test',
    'CoopTestCase',
    ]


def test_values_against_model(model_, expected_values):
    for k, v in expected_values.iteritems():
        value = getattr(model_, k)
        assert value == v, '"%s" should be "%s"' % (value, v)


def get_module_test_case(module_name):
    filename = os.path.abspath(os.path.join(os.path.normpath(__file__),
            '..', '..', module_name, 'tests', 'test_module.py'))
    return imp.load_source(module_name, filename)


def launch_function(module_name, method_name):
    master = Transaction().context.get('master', None)
    if not(master and '%s,%s' % (module_name, method_name)
            in master._executed):
        module_file = get_module_test_case(module_name)
        test_class = module_file.ModuleTestCase
        test_class._models = Transaction().context.get('master')._models
        getattr(test_class(method_name), method_name)()
        master._executed.append('%s,%s' % (module_name, method_name))


def prepare_test(*_args):
    for arg in _args:
        if not isinstance(arg, str) or isinstance(arg, unicode):
            raise Exception('Parameters must be strings, not %s' % type(arg))

    def decorator(f, forced=False):
        def wrap(*args, **kwargs):
            if not (Transaction() and Transaction().context and
                    'master' in Transaction().context):
                with Transaction().start(DB_NAME, USER, context=CONTEXT):
                    # Run all tests as root. Access management tests should
                    # manually set the user in the transaction
                    with Transaction().new_cursor(), Transaction().set_user(0):
                        with Transaction().set_context(master=args[0]):
                            args[0]._executed = []
                            for arg in _args:
                                module_name, method_name = arg.split('.')
                                launch_function(module_name, method_name)
                        if not forced:
                            result = f(args[0])
                        else:
                            result = f()
                        Transaction().cursor.rollback()
                        return result
            else:
                for arg in _args:
                    module_name, method_name = arg.split('.')
                    launch_function(module_name, method_name)
                if not forced:
                    return f(args[0])
                else:
                    return f()
        wrap._is_ready = True
        return wrap
    return decorator


class CoopTestCase(ModuleTestCase):
    'Coop Test Case'

    @classmethod
    def depending_modules(cls):
        return []

    @classmethod
    def get_test_cases_to_run(cls):
        return []

    @classmethod
    def install_module(cls):
        import trytond.tests.test_tryton
        trytond.tests.test_tryton.install_module(cls.module)

    def run(self, result=None):
        test_function = getattr(self, self._testMethodName)
        if not (hasattr(test_function, '_is_ready') and
                test_function._is_ready) and not (self._testMethodName in (
                        'test_view', 'test_depends', 'test_menu_action',
                        'test_model_access', 'test9999_launch_test_cases',
                        'test_rec_name', 'test_workflow_transitions',
                        'test_field_methods')):
            good_function = functools.partial(
                prepare_test()(test_function, True), self)
            setattr(self, self._testMethodName, good_function)
        super(CoopTestCase, self).run(result)

    @classmethod
    def get_models(cls):
        return {}

    @classmethod
    def get_all_modules(cls, modules):
        for module in cls.depending_modules() + [cls.module]:
            if module in modules:
                continue
            the_module = get_module_test_case(module)
            modules[module] = the_module
            the_module.ModuleTestCase.get_all_modules(modules)

    def setUp(self):
        import trytond.tests.test_tryton
        modules = {}
        self.get_all_modules(modules)
        for module in modules.itervalues():
            module.ModuleTestCase.install_module()

        models = {
            'TestCaseModel': 'ir.test_case',
            'Lang': 'ir.lang',
            }
        for module in modules.itervalues():
            models.update(module.ModuleTestCase.get_models())

        self._models = {}
        for k, v in models.iteritems():
            try:
                good_model = trytond.tests.test_tryton.POOL.get(v)
            except KeyError:
                good_model = trytond.tests.test_tryton.POOL.get(
                    v, type='wizard')
            self._models.update({k: good_model})

        from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            with Transaction().new_cursor(), Transaction().set_user(0):
                self.TestCaseModel.run_test_cases([
                        getattr(self.TestCaseModel, x)
                        for x in self.get_test_cases_to_run()])
                Transaction().cursor.commit()

    def test9999_launch_test_cases(self):
        if os.environ.get('DO_NOT_TEST_CASES'):
            return
        with Transaction().new_cursor():
            test_case_instance = self.TestCaseModel.get_instance()
            test_case_instance.language, = self.Lang.search([
                    ('code', '=', 'fr_FR')])
            test_case_instance.save()
            Transaction().cursor.commit()
        with Transaction().new_cursor(), Transaction().set_context(
                TESTING=True):
            self.TestCaseModel.run_all_test_cases()

    def __getattr__(self, name):
        if name == '_models':
            return super(CoopTestCase, self).__getattr__(name)
        if self._models and name in self._models:
            return self._models[name]
        raise AttributeError

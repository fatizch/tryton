import os
import imp
import unittest


def get_module_test_case(module_name):
    filename = os.path.abspath(
        os.path.join(
            os.path.normpath(__file__),
            '..', '..', module_name, 'tests', 'test_module.py'))
    return imp.load_source(module_name, filename)


class CoopTestCase(unittest.TestCase):
    'Coop Test Case'

    @classmethod
    def get_module_name(cls):
        raise NotImplementedError

    @classmethod
    def depending_modules(cls):
        return []

    @classmethod
    def install_module(cls):
        import trytond.tests.test_tryton
        trytond.tests.test_tryton.install_module(cls.get_module_name())

    @classmethod
    def get_models(cls):
        return {}

    @classmethod
    def get_all_modules(cls, modules):
        for module in cls.depending_modules() + [cls.get_module_name()]:
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

        models = {}
        for modules in modules.itervalues():
            models.update(modules.ModuleTestCase.get_models())

        for k, v in models.iteritems():
            try:
                good_model = trytond.tests.test_tryton.POOL.get(v)
            except KeyError:
                good_model = trytond.tests.test_tryton.POOL.get(
                    v, type='wizard')
            setattr(self, k, good_model)

    def test0005views(self):
        '''
        Test views.
        '''
        import trytond.tests.test_tryton
        trytond.tests.test_tryton.test_view(self.get_module_name())

    def test0006depends(self):
        '''
        Test depends.
        '''
        import trytond.tests.test_tryton
        trytond.tests.test_tryton.test_depends()

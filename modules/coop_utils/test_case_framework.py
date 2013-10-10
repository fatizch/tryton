import logging

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import Button, StateView, StateTransition
import model
import fields
import export


__all__ = [
    'TestCaseModel',
    'TestCaseSelector',
    'SelectTestCase',
    'TestCaseFileSelector',
    'LoadTestCaseFiles',
    'TestCaseWizard',
    'add_dependencies',
    ]


def run_test_case_method(source_class, method):
    # Runner function that will be used to automatically call before / after
    # methods. It supports chained before / after though the use of this
    # possibility is not recommanded
    method_name = method.__name__
    before_meth = getattr(source_class, '_before_%s' % method_name, None)
    if before_meth:
        run_test_case_method(source_class, before_meth)
    logging.getLogger('test_case').info('Executing test_case %s' %
        method.__name__)
    method()
    after_meth = getattr(source_class, '_after_%s' % method_name, None)
    if after_meth:
        run_test_case_method(source_class, after_meth)


def add_dependencies(name, *args):
    # A decorator for test_case functions to be able to build the dependency
    # tree of test_cases
    def wrapper(f):
        if hasattr(f, '_dependencies'):
            f._dependencies = list(set(f._dependencies, args))
        else:
            f._dependencies = list(set(args))
        f._test_case_name = name
        return f
    return wrapper


def solve_graph(node_name, nodes, resolved=None, unresolved=None):
    if node_name is None:
        resolved = []
        unresolved = []
        for name in nodes.iterkeys():
            solve_graph(name, nodes, resolved, unresolved)
        return resolved
    unresolved.append(node_name)
    for node_dep in nodes[node_name]:
        if node_dep not in resolved:
            if node_dep in unresolved:
                raise Exception('Circular reference : %s => %s' % (
                        node_name, node_dep))
            solve_graph(node_dep, nodes, resolved, unresolved)
    if node_name not in resolved:
        resolved.append(node_name)
    unresolved.remove(node_name)


def build_dependency_graph(cls, methods):
    # This method will return an ordered list for execution for the selected
    # test cases methods.
    method_dict = dict([(method.__name__, method) for method in methods])
    method_dependencies = {}
    to_explore = methods[:]
    while to_explore:
        method = to_explore.pop()
        method_dependencies[method.__name__] = method._dependencies[:]
        for dep in method_dependencies[method.__name__]:
            if dep not in method_dict:
                method_dict[dep] = getattr(cls, dep)
                to_explore.append(method_dict[dep])

    cache_res = {}

    def get_deps(method, res=None):
        if method.__name__ in cache_res:
            return cache_res[method.__name__]
        add2cache = False
        if not res:
            res = set([])
            add2cache = True
        for elem in method._dependencies:
            res.add(elem)
            get_deps(method_dict[elem], res)
        if add2cache:
            cache_res[method.__name__] = list(res)
            return cache_res[method.__name__]

    dependencies = {}
    final_dependencies = {}
    for k, v in method_dependencies.iteritems():
        final = dependencies.get(k, [[], []])[0]
        found = dependencies.get(k, [[], []])[1]
        for dep in v:
            if dep in found:
                continue
            for new_dep in get_deps(method_dict[dep]):
                if new_dep in final:
                    final.pop(final.index(new_dep))
                    continue
                if new_dep in found:
                    continue
                found.append(new_dep)
            final.append(dep)
            found.append(dep)
        dependencies[k] = [list(set(final)), list(set(found))]
        final_dependencies[k] = dependencies[k][0]

    result = solve_graph(None, final_dependencies)
    return (getattr(cls, x) for x in result)


class TestCaseModel(model.CoopView):
    'Test Case Model'

    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def run_test_case(cls, test_case):
        run_test_case_method(cls, test_case)

    @classmethod
    def run_test_cases(cls, test_cases):
        order = build_dependency_graph(TestCaseModel, test_cases)
        for elem in order:
            cls.run_test_case(elem)

    @classmethod
    def run_all_test_cases(cls):
        cls.run_test_cases(cls.get_all_tests())

    @classmethod
    def get_all_tests(cls):
        for elem in [getattr(TestCaseModel, x) for x in dir(TestCaseModel)]:
            if not hasattr(elem, '_test_case_name'):
                continue
            yield elem

    @classmethod
    @add_dependencies('Party Test Case')
    def party_test_case(cls):
        pass

    @classmethod
    @add_dependencies('Bank Test Case', 'party_test_case')
    def bank_test_case(cls):
        pass

    @classmethod
    @add_dependencies('Product Test Case', 'party_test_case')
    def product_test_case(cls):
        pass

    @classmethod
    @add_dependencies('Contract Test Case', 'product_test_case')
    def contract_test_case(cls):
        pass


class TestCaseSelector(model.CoopView):
    'Test Case Selector'

    __name__ = 'coop_utils.test_case_selector'

    method_name = fields.Char('Method Name')
    name = fields.Char('Test Case Name')
    selected = fields.Boolean('Will be executed', states={'readonly':
            Eval('selection') == 'automatic'},)
    selection = fields.Selection([
            ('automatic', 'Automatic'),
            ('manual', 'Manual'),
            ('not_selected', 'Not Selected')], 'Selection')


class SelectTestCase(model.CoopView):
    'Select Test Case'

    __name__ = 'coop_utils.select_test_cases'

    select_all = fields.Boolean('Select All', on_change=['select_all',
            'test_cases'])
    test_cases = fields.One2Many('coop_utils.test_case_selector', None,
        'Test Cases', on_change=['test_cases'])

    def on_change_test_cases(self):
        TestCaseModel = Pool().get('coop_utils.test_case_model')
        selected = [elem for elem in self.test_cases
            if elem.selection in ('manual', 'not_selected') and elem.selected]
        order = [y.__name__ for y in build_dependency_graph(TestCaseModel, [
                getattr(TestCaseModel, x.method_name) for x in selected])]
        to_update = []
        for x in self.test_cases:
            if x.method_name not in order:
                to_update.append({
                        'id': x.id,
                        'selected': False,
                        'selection': 'not_selected'})
                continue
            to_update.append({
                    'id': x.id,
                    'selected': True,
                    'selection': 'manual' if x in selected else 'automatic'})
        return {'test_cases': {'update': to_update}}

    def on_change_select_all(self):
        return {
            'test_cases': {'update': [{
                        'id': x.id,
                        'selection': 'manual' if self.select_all else
                        'not_selected',
                        'selected': self.select_all}
                    for x in self.test_cases]}}


class TestCaseFileSelector(model.CoopView):
    'Test Case File Selector'

    __name__ = 'coop_utils.test_case_file_selector'

    selected = fields.Boolean('Will be loaded')
    filename = fields.Char('File name', states={'readonly': True})
    full_path = fields.Char('Full Path')


class LoadTestCaseFiles(model.CoopView):
    'Load Test Case Files'

    __name__ = 'coop_utils.load_test_case_files'

    select_all = fields.Boolean('Select All', on_change=['select_all',
            'test_files'])
    test_files = fields.One2Many('coop_utils.test_case_file_selector', None,
        'Test Files')

    def on_change_select_all(self):
        return {
            'test_files': {'update': [{
                        'id': x.id,
                        'selected': self.select_all}
                    for x in self.test_files]}}


class TestCaseWizard(model.CoopWizard):
    'Test Case Wizard'

    __name__ = 'coop_utils.test_case_wizard'

    start_state = 'select_test_cases'
    select_test_cases = StateView('coop_utils.select_test_cases',
        'coop_utils.select_test_cases_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Execute', 'execute_test_cases', 'tryton-ok')])
    execute_test_cases = StateTransition()
    select_files = StateView('coop_utils.load_test_case_files',
        'coop_utils.load_test_case_files_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Load', 'load_files', 'tryton-ok')])
    load_files = StateTransition()

    @classmethod
    def __setup__(cls):
        super(TestCaseWizard, cls).__setup__()
        cls._error_messages.update({
            'bad_json': 'Cannot load test case file %s',
        })

    def default_select_test_cases(self, name):
        TestCaseModel = Pool().get('coop_utils.test_case_model')
        test_cases = []
        for elem in TestCaseModel.get_all_tests():
            test_cases.append({
                    'method_name': elem.__name__,
                    'name': elem._test_case_name,
                    'selected': False,
                    'selection': 'not_selected',
                    })
        return {'test_cases': test_cases}

    def transition_execute_test_cases(self):
        TestCaseModel = Pool().get('coop_utils.test_case_model')
        to_execute = []
        for test_case in self.select_test_cases.test_cases:
            if test_case.selection == 'manual':
                to_execute.append(
                    getattr(TestCaseModel, test_case.method_name))
        if not to_execute:
            return 'select_files'
        TestCaseModel.run_test_cases(to_execute)
        return 'select_files'

    def default_select_files(self, name):
        import os
        DIR = os.path.abspath(os.path.normpath(os.path.join(
                    __file__, '..', 'json_files')))
        file_names = [f for f in os.listdir(DIR)
            if os.path.isfile(os.path.join(DIR, f)) and f.endswith('.json')]
        test_files = []
        for file_name in file_names:
            test_files.append({
                    'filename': file_name,
                    'full_path': os.path.join(DIR, f)})
        return {'test_files': test_files}

    def transition_load_files(self):
        for elem in self.select_files.test_files:
            if not elem.selected:
                continue
            with open(elem.full_path, 'rb') as the_file:
                logging.getLogger('test_case').info('Loading json file %s' %
                    elem.filename)
                try:
                    export.ExportImportMixin.import_json(the_file.read())
                    logging.getLogger('test_case').info('Successfully '
                        'imported %s' % elem.filename)
                except:
                    logging.getLogger('test_case').info('Failed to import %s' %
                        elem.filename)
                    self.raise_user_error('bad_json', (elem.filename))
        return 'end'

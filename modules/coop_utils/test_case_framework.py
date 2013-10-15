import os
import csv
import polib
import logging
import random

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import Button, StateView, StateTransition
from trytond.model import ModelSingleton
from trytond.transaction import Transaction
from trytond.cache import Cache
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
    'set_test_case',
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
    result = method()
    if result:
        source_class.save_objects(result)
    after_meth = getattr(source_class, '_after_%s' % method_name, None)
    if after_meth:
        run_test_case_method(source_class, after_meth)


def set_test_case(name, *args):
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
    cls = Pool().get(cls.__name__)
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


class TestCaseModel(ModelSingleton, model.CoopSQL, model.CoopView):
    'Test Case Model'

    __name__ = 'coop_utils.test_case_model'

    language = fields.Many2One('ir.lang', 'Test Case Language')

    @classmethod
    def default_language(cls):
        return 1

    @classmethod
    def get_instance(cls):
        return cls.get_singleton()

    @classmethod
    def get_language(cls):
        return cls.get_singleton().language

    @classmethod
    def get_logger(cls):
        return logging.getLogger('test_case')

    @classmethod
    def run_test_case(cls, test_case):
        with Transaction().new_cursor(), Transaction().set_user(0):
            run_test_case_method(cls, test_case)
            Transaction().cursor.commit()

    @classmethod
    def clear_all_caches(cls):
        GoodModel = Pool().get(cls.__name__)
        for elem in [getattr(GoodModel, x) for x in dir(GoodModel)]:
            if not isinstance(elem, Cache):
                continue
            elem.clear()

    @classmethod
    def run_test_cases(cls, test_cases):
        cls.clear_all_caches()
        try:
            cls._loaded_resources = {}
            order = build_dependency_graph(TestCaseModel, test_cases)
            for elem in order:
                cls.run_test_case(elem)
        finally:
            del cls._loaded_resources
            cls.clear_all_caches()

    @classmethod
    def run_all_test_cases(cls):
        cls.run_test_cases(cls.get_all_tests())

    @classmethod
    def get_all_tests(cls):
        GoodModel = Pool().get(cls.__name__)
        for elem in [getattr(GoodModel, x) for x in dir(GoodModel)]:
            if not hasattr(elem, '_test_case_name'):
                continue
            yield elem

    @classmethod
    def global_search_list(cls):
        return set([])

    @classmethod
    def save_objects(cls, objects):
        GoodModel = Pool().get(cls.__name__)
        group = {}
        for elem in objects:
            if elem._export_find_instance(elem._export_get_key()):
                continue
            if not elem.__name__ in group:
                group[elem.__name__] = []
            group[elem.__name__].append(elem)
        for class_name, elems in group.iteritems():
            save_method_hook = '_save_%s' % (
                class_name.replace('.', '_').replace('-', '_'))
            if hasattr(GoodModel, save_method_hook):
                getattr(GoodModel, save_method_hook)(elems)
            for elem in elems:
                elem.save()

    @classmethod
    @set_test_case('Set Global Search')
    def set_global_search(cls):
        Model = Pool().get('ir.model')
        targets = Model.search([
                ('model', 'in', cls.global_search_list())])
        Model.write(targets, {'global_search_p': True})

    @classmethod
    def read_data_file(cls, filename, sep='|'):
        res = {}
        cur_model = ''
        cur_data = []
        lines = open(filename).readlines()
        for line in lines:
            line = line[:-1]
            line.rstrip()
            if line == '':
                continue
            if line[0] == '[' and line[-1] == ']':
                if cur_model and cur_data:
                    res[cur_model] = cur_data
                cur_model = line[1:-1]
                cur_data = []
                continue
            cur_data.append(line.split(sep))

        res[cur_model] = cur_data

        return res

    @classmethod
    def read_list_file(cls, filename, module):
        cls.load_resources(module)
        if isinstance(cls._loaded_resources[module]['files'][filename], list):
            return cls._loaded_resources[module]['files'][filename]
        with open(cls._loaded_resources[module]['files'][filename], 'r') as f:
            res = []
            n = 0
            for line in f:
                res.append(line.decode('utf8').strip())
                n += 1
        cls._loaded_resources[module]['files'][filename] = res
        return res

    @classmethod
    def read_csv_file(cls, filename, module, sep=';', reader=''):
        cls.load_resources(module)
        if isinstance(cls._loaded_resources[module]['files'][filename], list):
            return cls._loaded_resources[module]['files'][filename]
        with open(cls._loaded_resources[module]['files'][filename], 'r') as f:
            if not reader:
                good_reader = csv.reader
            elif reader == 'dict':
                good_reader = csv.DictReader
            reader = good_reader(f, delimiter=sep)
            res = []
            for line in reader:
                res.append(line)
        cls._loaded_resources[module]['files'][filename] = res
        return res

    @classmethod
    def launch_dice(cls, probability):
        return random.randint(0, 99) < probability

    @classmethod
    def translate_this(cls, msg_id, module_name):
        cls.load_resources(module_name)
        return cls._loaded_resources[module_name]['translations'][msg_id]

    @classmethod
    def load_resources(cls, modules_to_load=None):
        if not hasattr(cls, '_loaded_resources'):
            cls._loaded_resources = {}
        if isinstance(modules_to_load, basestring):
            modules_to_load = [modules_to_load]
        elif modules_to_load is None:
            Module = Pool().get('ir.module.module')
            modules_to_load = [x.name
                for x in Module.search([('state', '=', 'installed')])]
        # trytond/trytond/modules path
        top_path = os.path.abspath(os.path.join(os.path.normpath(__file__),
                '..', '..'))
        language_path = cls.get_language().code
        for module_name in modules_to_load:
            if module_name in cls._loaded_resources:
                continue
            resource_path = os.path.join(top_path, module_name,
                'test_case_data', language_path)
            result = {
                'files': {},
                'translations': {}}
            if not os.path.exists(resource_path) or not os.path.isdir(
                    resource_path):
                cls._loaded_resources[module_name] = result
                continue
            for file_name in os.listdir(resource_path):
                if file_name.endswith('.po'):
                    po = polib.pofile(os.path.join(resource_path, file_name))
                    for entry in po.translated_entries():
                        result['translations'][entry.msgid] = entry.msgstr
                    continue
                result['files'][u'%s' % file_name] = os.path.join(
                    resource_path, file_name)
            cls._loaded_resources[module_name] = result


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

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
    'TestCaseWizard',
    ]


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
    dependency_data = cls._get_test_case_dependencies()
    method_dict = dict([(method.__name__, method) for method in methods])
    method_dependencies = {}
    to_explore = methods[:]
    while to_explore:
        method = to_explore.pop()
        method_dependencies[method.__name__] = dependency_data[
            method.__name__]['dependencies'].copy()
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
        for elem in dependency_data[method.__name__]['dependencies']:
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
    def run_test_case_method(cls, method):
        # Runner function that will be used to automatically call before /
        # after methods. It supports chained before / after though the use of
        # this possibility is not recommanded
        method_name = method.__name__
        before_meth = getattr(cls, '_before_%s' % method_name, None)
        if before_meth:
            cls.run_test_case_method(before_meth)
        logging.getLogger('test_case').info('Executing test_case %s' %
            method.__name__)
        result = method()
        if result:
            cls.save_objects(result)
        after_meth = getattr(cls, '_after_%s' % method_name, None)
        if after_meth:
            cls.run_test_case_method(after_meth)

    @classmethod
    def _get_test_case_dependencies(cls):
        return {
            'set_global_search': {
                'name': 'Set Global Search',
                'dependencies': set([])},
            'set_language_translatable': {
                'name': 'Set translatable languages',
                'dependencies': set([])},
            }

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
            cls.run_test_case_method(test_case)
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
                try:
                    cls.run_test_case(elem)
                except:
                    logging.getLogger('test_case').warning('Error executing '
                        'test case %s' % elem.__name__)
                    raise
        finally:
            del cls._loaded_resources
            cls.clear_all_caches()

    @classmethod
    def run_all_test_cases(cls):
        cls.run_test_cases(cls.get_all_tests())

    @classmethod
    def get_all_tests(cls):
        result = []
        for elem in cls._get_test_case_dependencies().keys():
            result.append(getattr(cls, elem))
        return result

    @classmethod
    def get_test_data(cls):
        for k, v in cls._get_test_case_dependencies().iteritems():
            yield getattr(cls, k), k, v

    @classmethod
    def global_search_list(cls):
        return set([])

    @classmethod
    def save_objects(cls, objects):
        GoodModel = Pool().get(cls.__name__)
        group = {}
        for elem in objects:
            if not elem.__name__ in group:
                group[elem.__name__] = []
            group[elem.__name__].append(elem)
        for class_name, elems in group.iteritems():
            force_save = False
            if not elems[0]._export_keys():
                force_save = True
                cls.get_logger().warning('Unable to get export keys for '
                    'model %s, no check will be done when saving' % class_name)
            save_method_hook = '_save_%s' % (
                class_name.replace('.', '_').replace('-', '_'))
            if hasattr(GoodModel, save_method_hook):
                getattr(GoodModel, save_method_hook)(elems)
            for elem in elems:
                try:
                    if force_save or not elem._export_find_instance(
                            elem._export_get_key()):
                        elem.save()
                except export.NotExportImport:
                    # Known Exception is _export_find_instance raising a
                    # multiple found error due to bad key definition. As a key
                    # is currently not properly se on some models
                    # (party.party), we just re-save if it happens
                    elem.save()

    @classmethod
    def set_global_search(cls):
        Model = Pool().get('ir.model')
        targets = Model.search([
                ('model', 'in', cls.global_search_list())])
        Model.write(targets, {'global_search_p': True})

    @classmethod
    def set_language_translatable(cls):
        Lang = Pool().get('ir.lang')
        langs = Lang.search([
                ('translatable', '=', False),
                ('code', 'in', ['fr_FR', 'en_US'])])
        # We force the write on existing records, do not use the auto-save on
        # test_case return values
        Lang.write(langs, {'translatable': True})

    @classmethod
    def read_data_file(cls, filename, module, sep='|'):
        cls.load_resources(module)
        if isinstance(cls._loaded_resources[module]['files'][filename], (
                    list, dict)):
            return cls._loaded_resources[module]['files'][filename]
        res, cur_model, cur_data = {}, '', []
        with open(cls._loaded_resources[module]['files'][filename], 'r') as f:
            for line in f:
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
            if cur_model:
                res[cur_model] = cur_data
            else:
                res = cur_data
        cls._loaded_resources[module]['files'][filename] = res
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

    @classmethod
    def get_translater(cls, module):
        return lambda x: cls.translate_this(x, module)

    @classmethod
    def get_all_test_files(cls):
        Module = Pool().get('ir.module.module')
        result = {}
        # trytond/trytond/modules path
        top_path = os.path.abspath(os.path.join(os.path.normpath(__file__),
                '..', '..', '..', 'modules'))
        language_path = Pool().get(
            'coop_utils.test_case_model').get_language().code
        modules_to_load = [x.name
            for x in Module.search([('state', '=', 'installed')])]
        for module in modules_to_load:
            file_path = os.path.join(top_path, module, 'test_case_data',
                language_path)
            if not os.path.exists(file_path) or not os.path.isdir(
                    file_path):
                continue
            for file_name in os.listdir(file_path):
                if not file_name.endswith('.json'):
                    continue
                result[u'%s' % file_name] = os.path.join(
                    file_path, file_name)
        return result


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


class TestCaseFileSelector(model.CoopView):
    'Test Case File Selector'

    __name__ = 'coop_utils.test_case_file_selector'

    selected = fields.Boolean('Will be loaded')
    filename = fields.Char('File name', states={'readonly': True})
    full_path = fields.Char('Full Path')


class SelectTestCase(model.CoopView):
    'Select Test Case'

    __name__ = 'ir.test_case.run.select'

    select_all_test_cases = fields.Boolean('Select All',
        on_change=['select_all_test_cases', 'test_cases'])
    select_all_files = fields.Boolean('Select All',
        on_change=['select_all_files', 'test_files'])
    test_cases = fields.One2Many('coop_utils.test_case_selector', None,
        'Test Cases', on_change=['test_cases'])
    test_files = fields.One2Many('coop_utils.test_case_file_selector', None,
        'Test Files')

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

    def on_change_select_all_test_cases(self):
        if not (hasattr(self, 'test_cases') and self.test_cases):
            return {}
        return {
            'test_cases': {'update': [{
                        'id': x.id,
                        'selection': 'manual' if self.select_all_test_cases
                        else 'not_selected',
                        'selected': self.select_all_test_cases}
                    for x in self.test_cases]}}

    def on_change_select_all_files(self):
        if not (hasattr(self, 'test_files') and self.test_files):
            return {}
        return {
            'test_files': {'update': [{
                        'id': x.id,
                        'selected': self.select_all_files}
                    for x in self.test_files]}}


class TestCaseWizard(model.CoopWizard):
    'Test Case Wizard'

    __name__ = 'coop_utils.test_case_wizard'

    start_state = 'select_test_cases'
    select_test_cases = StateView('ir.test_case.run.select',
        'coop_utils.select_test_cases_form', [
            Button('Quit', 'end', 'tryton-cancel'),
            Button('Execute Selected', 'execute_test_cases', 'tryton-ok')])
    execute_test_cases = StateTransition()
    load_files = StateTransition()

    @classmethod
    def __setup__(cls):
        super(TestCaseWizard, cls).__setup__()
        cls._error_messages.update({
            'bad_json': 'Cannot load test case file %s',
        })

    def default_select_test_cases(self, name):
        # Look for files
        test_files = []
        files = Pool().get(
            'coop_utils.test_case_model').get_all_test_files()
        for file_name, file_path in files.iteritems():
            test_files.append({
                    'filename': file_name,
                    'full_path': file_path})
        result = {'test_files': test_files}

        # Look for test cases
        TestCaseModel = Pool().get('coop_utils.test_case_model')
        test_cases = []
        for _, name, info in TestCaseModel.get_test_data():
            test_cases.append({
                    'method_name': name,
                    'name': info['name'],
                    'selected': False,
                    'selection': 'not_selected',
                    })
        test_cases.sort(key=lambda x: x['name'])
        result['test_cases'] = test_cases
        return result

    def transition_execute_test_cases(self):
        TestCaseModel = Pool().get('coop_utils.test_case_model')
        to_execute = []
        for test_case in self.select_test_cases.test_cases:
            if test_case.selection == 'manual':
                to_execute.append(
                    getattr(TestCaseModel, test_case.method_name))
        if to_execute:
            TestCaseModel.run_test_cases(to_execute)
        return 'load_files'

    def transition_load_files(self):
        for elem in self.select_test_cases.test_files:
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
                    raise
                    self.raise_user_error('bad_json', (elem.filename))
        return 'select_test_cases'

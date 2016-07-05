# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import csv
import polib
import logging
import random
import datetime

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond import backend
from trytond.wizard import Button, StateView, StateTransition
from trytond.model import ModelSingleton
from trytond.transaction import Transaction
from trytond.cache import Cache
import model
import fields
import export


__all__ = [
    'TestCaseModel',
    'TestCaseInstance',
    'TestCaseRequirementRelation',
    'TestCaseSelector',
    'SelectTestCase',
    'TestCaseFileSelector',
    'TestCaseWizard',
    ]


class TestCaseModel(ModelSingleton, model.CoopSQL, model.CoopView):
    'Test Case Model'

    __name__ = 'ir.test_case'

    language = fields.Many2One('ir.lang', 'Test Case Language',
        ondelete='RESTRICT')
    test_cases = fields.One2Many('ir.test_case.instance', 'config',
        'Test Cases', readonly=True, delete_missing=True,
        target_not_indexed=True)

    @classmethod
    def check_xml_record(cls, records, values):
        # Override to allow to modify the base configuration
        return True

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
        cur_user = Transaction().user
        DatabaseOperationalError = backend.get('DatabaseOperationalError')
        must_be_executed = not test_case.executed
        if test_case.test_method_name:
            must_be_executed = getattr(cls, test_case.test_method_name)()
        if not must_be_executed:
            logging.getLogger('test_case').info('Not executing test_case "%s",'
                ' already executed' % test_case.name)
            return
        with Transaction().new_transaction() as transaction, \
                Transaction().set_user(0):
            with Transaction().set_context(user=cur_user if cur_user else 1):
                cls.run_test_case_method(getattr(cls, test_case.method_name))
                test_case.execution_date = datetime.datetime.now()
                test_case.save()
            try:
                transaction.commit()
            except DatabaseOperationalError:
                transaction.rollback()

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
            order = cls.build_dependency_graph(test_cases)
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
        return cls.get_instance().test_cases

    @classmethod
    def global_search_list(cls):
        return set([])

    @classmethod
    def save_objects(cls, objects):
        GoodModel = Pool().get(cls.__name__)
        group = {}
        for elem in objects:
            if elem.__name__ not in group:
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
    def set_global_search(cls):
        Model = Pool().get('ir.model')
        targets = Model.search([('model', 'in', cls.global_search_list())])
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
        if isinstance(cls._loaded_resources[module]['files'][filename],
                (list, dict)):
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
        if cls.get_language().code == 'en_US':
            return msg_id
        cls.load_resources(module_name)
        return cls._loaded_resources[module_name]['translations'][msg_id]

    @classmethod
    def load_resources(cls, modules_to_load=None):
        if not hasattr(cls, '_loaded_resources'):
            cls._loaded_resources = {}
        if isinstance(modules_to_load, basestring):
            modules_to_load = [modules_to_load]
        elif modules_to_load is None:
            Module = Pool().get('ir.module')
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
        Module = Pool().get('ir.module')
        result = {}
        # trytond/trytond/modules path
        top_path = os.path.abspath(os.path.join(os.path.normpath(__file__),
                '..', '..', '..', 'modules'))
        language_path = Pool().get(
            'ir.test_case').get_language().code
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

    @classmethod
    def solve_graph(cls, node_name, nodes, resolved=None, unresolved=None):
        if node_name is None:
            resolved = []
            unresolved = []
            for name in nodes.iterkeys():
                cls.solve_graph(name, nodes, resolved, unresolved)
            return resolved
        unresolved.append(node_name)
        for node_dep in nodes[node_name]:
            if node_dep not in resolved:
                if node_dep in unresolved:
                    raise Exception('Circular reference : %s => %s' % (
                            node_name, node_dep))
                cls.solve_graph(node_dep, nodes, resolved, unresolved)
        if node_name not in resolved:
            resolved.append(node_name)
        unresolved.remove(node_name)

    @classmethod
    def build_dependency_graph(cls, test_cases):
        # This method will return an ordered list for execution for the
        # selected test cases methods.
        cls = Pool().get(cls.__name__)
        methods = list(test_cases)
        method_dependencies = {}
        to_explore = list(test_cases)
        while to_explore:
            test_case = to_explore.pop()
            method_dependencies[test_case] = list(test_case.requirements)
            for dep in method_dependencies[test_case]:
                if dep not in methods:
                    methods.append(dep)
                    to_explore.append(dep)

        cache_res = {}

        def get_deps(test_case, res=None):
            if test_case in cache_res:
                return cache_res[test_case]
            add2cache = False
            if not res:
                res = set([])
                add2cache = True
            for elem in test_case.requirements:
                res.add(elem)
                get_deps(elem, res)
            if add2cache:
                cache_res[test_case] = list(res)
                return cache_res[test_case]

        dependencies = {}
        final_dependencies = {}
        for k, v in method_dependencies.iteritems():
            final = dependencies.get(k, [[], []])[0]
            found = dependencies.get(k, [[], []])[1]
            for dep in v:
                if dep in found:
                    continue
                for new_dep in get_deps(dep):
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

        return cls.solve_graph(None, final_dependencies)


class TestCaseInstance(model.CoopSQL, model.CoopView):
    'Test Case Instance'

    __name__ = 'ir.test_case.instance'

    config = fields.Many2One('ir.test_case', 'Configuration',
        ondelete='CASCADE', required=True)
    execution_date = fields.DateTime('Execution Date')
    method_name = fields.Char('Method Name', required=True)
    test_method_name = fields.Char('Test Method Name', help='The name of the '
        'method that will be used to decide whether the Test Case should be '
        'run or not')
    name = fields.Char('Name', required=True, translate=True)
    requirements = fields.Many2Many(
        'ir.test_case.instance-ir.test_case.instance', 'parent', 'child',
        'Requirements')
    executed = fields.Function(
        fields.Boolean('Executed'),
        'get_executed')

    @classmethod
    def __setup__(cls):
        super(TestCaseInstance, cls).__setup__()
        cls._error_messages.update({
                'non_existing_test_case': 'Test Case %s uses the %s method, '
                'which does not exist !',
                })

    @classmethod
    def default_config(cls):
        return 1

    @classmethod
    def validate(cls, test_cases):
        TestCaseModel = Pool().get('ir.test_case')
        for test in test_cases:
            if getattr(TestCaseModel, test.method_name, None) is None:
                cls.raise_user_error('non_existing_test_case', (test.name,
                        test.method_name))
            if not test.test_method_name:
                continue
            if getattr(TestCaseModel, test.test_method_name) is None:
                cls.raise_user_error('non_existing_test_case', (test.name,
                        test.test_method_name))

    @classmethod
    def check_xml_record(cls, records, values):
        # Override to allow to modify the base configuration
        return True

    def get_executed(self, name):
        return self.execution_date is not None

    def get_rec_name(self, name):
        return '%s%s' % ('[Executed] ' if self.executed else '', self.name)

    @classmethod
    def run_test_case(cls, test_cases):
        Pool().get('ir.test_case').run_test_cases([test_cases])


class TestCaseRequirementRelation(model.CoopSQL):
    'Test Case Requirement Relation'

    __name__ = 'ir.test_case.instance-ir.test_case.instance'

    child = fields.Many2One('ir.test_case.instance', 'Child',
        ondelete='CASCADE')
    parent = fields.Many2One('ir.test_case.instance', 'Parent',
        ondelete='RESTRICT')


class TestCaseSelector(model.CoopView):
    'Test Case Selector'

    __name__ = 'ir.test_case.run.select.method'

    test_case = fields.Many2One('ir.test_case.instance', 'Test Case')
    test = fields.Char('Test')
    selected = fields.Boolean('Will be executed', states={'readonly':
            Eval('selection') == 'automatic'},)
    selection = fields.Selection([
            ('automatic', 'Automatic'),
            ('manual', 'Manual'),
            ('not_selected', 'Not Selected')], 'Selection')


class TestCaseFileSelector(model.CoopView):
    'Test Case File Selector'

    __name__ = 'ir.test_case.run.select.file'

    selected = fields.Boolean('Will be loaded')
    filename = fields.Char('File name', states={'readonly': True})
    full_path = fields.Char('Full Path')


class SelectTestCase(model.CoopView):
    'Select Test Case'

    __name__ = 'ir.test_case.run.select'

    select_all_test_cases = fields.Boolean('Select All')
    select_all_files = fields.Boolean('Select All')
    test_cases = fields.One2Many('ir.test_case.run.select.method', None,
        'Test Cases')
    test_files = fields.One2Many('ir.test_case.run.select.file', None,
        'Test Files')

    @fields.depends('test_cases')
    def on_change_test_cases(self):
        TestCaseModel = Pool().get('ir.test_case')
        selected = [elem for elem in self.test_cases
            if elem.selection in ('manual', 'not_selected') and elem.selected]
        order = TestCaseModel.build_dependency_graph(
            [x.test_case for x in selected])
        for x in self.test_cases:
            if x.test_case not in order:
                x.selected = False
                x.selection = 'not_selected'
                continue
            x.selected = True
            x.selection = 'manual' if x in selected else 'automatic'
        self.test_cases = self.test_cases

    @fields.depends('select_all_test_cases', 'test_cases')
    def on_change_select_all_test_cases(self):
        if not self.test_cases:
            return
        for test_case in self.test_cases:
            test_case.selection = 'manual' if self.select_all_test_cases \
                        else 'not_selected',
            test_case.selected = self.select_all_test_cases
        self.test_cases = self.test_cases

    @fields.depends('select_all_files', 'test_files')
    def on_change_select_all_files(self):
        if not self.test_files:
            return
        for test_file in self.test_files:
            test_file.selected = self.select_all_files
        self.test_files = self.test_files


class TestCaseWizard(model.CoopWizard):
    'Test Case Wizard'

    __name__ = 'ir.test_case.run'

    start_state = 'select_test_cases'
    select_test_cases = StateView('ir.test_case.run.select',
        'cog_utils.test_case_run_select_form', [
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
            'ir.test_case').get_all_test_files()
        for file_name, file_path in files.iteritems():
            test_files.append({
                    'filename': file_name,
                    'full_path': file_path})
        result = {'test_files': test_files}

        # Look for test cases
        TestCaseModel = Pool().get('ir.test_case')
        test_cases = []
        for test_case in TestCaseModel.get_all_tests():
            test_cases.append({
                    'test_case': test_case.id,
                    'test': test_case.rec_name,
                    'selected': False,
                    'selection': 'not_selected',
                    })
        test_cases.sort(key=lambda x: x['test'])
        result['test_cases'] = test_cases
        return result

    def transition_execute_test_cases(self):
        TestCaseModel = Pool().get('ir.test_case')
        to_execute = []
        for test_case in self.select_test_cases.test_cases:
            if test_case.selection == 'manual':
                to_execute.append(test_case.test_case)
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
                    cur_user = Transaction().user
                    DatabaseOperationalError = backend.get(
                        'DatabaseOperationalError')
                    with Transaction().new_transaction() as transaction, \
                            Transaction().set_user(0):
                        if cur_user:
                            with Transaction().set_context(user=cur_user):
                                export.ExportImportMixin.import_json(
                                    the_file.read())
                        else:
                                export.ExportImportMixin.import_json(
                                    the_file.read())
                        try:
                            transaction.commit()
                        except DatabaseOperationalError:
                            transaction.rollback()
                    logging.getLogger('test_case').info('Successfully '
                        'imported %s' % elem.filename)
                except:
                    logging.getLogger('test_case').error('Failed to import %s'
                        % elem.filename)
                    raise
                    self.raise_user_error('bad_json', (elem.filename))
        return 'select_test_cases'

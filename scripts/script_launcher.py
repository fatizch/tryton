#!/usr/bin/env python
# encoding: utf-8
# PYTHON_ARGCOMPLETE_OK
import shutil
import os
import ConfigParser
import argparse
import argcomplete
import subprocess
import datetime

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def init_work_data(config):
    result = {}
    virtual_env_path = os.environ['VIRTUAL_ENV']
    result['virtual_env'] = virtual_env_path
    result['python_exec'] = os.path.join(virtual_env_path, 'bin', 'python')
    result['runtime_dir'] = os.path.join(virtual_env_path, config.get(
            'parameters', 'runtime_dir'))
    result['trytond_exec'] = os.path.join(virtual_env_path, config.get(
            'parameters', 'runtime_dir'), 'trytond', 'bin', 'trytond')
    result['tryton_exec'] = os.path.join(virtual_env_path, config.get(
            'parameters', 'runtime_dir'), 'tryton', 'bin', 'tryton')
    result['trytond_conf'] = os.path.join(virtual_env_path, config.get(
            'parameters', 'runtime_dir'), 'conf', 'trytond.conf')
    result['tryton_conf'] = os.path.join(virtual_env_path, config.get(
            'parameters', 'runtime_dir'), 'conf', 'tryton.conf')
    result['tests_conf'] = os.path.join(virtual_env_path, config.get(
            'parameters', 'runtime_dir'), 'conf', 'tests.conf')
    result['tryton_script_launcher'] = os.path.join(result['runtime_dir'],
        'coopbusiness', 'scripts', 'python_scripts', 'launch_tryton_script.py')
    result['trytond_test_runner'] = os.path.join(result['runtime_dir'],
        'trytond', 'trytond', 'tests', 'run-tests.py')
    result['coop_modules'] = os.path.join(result['runtime_dir'],
        'coopbusiness', 'modules')
    result['modules'] = os.path.join(result['runtime_dir'], 'trytond',
        'trytond', 'modules')
    return result


def find_matching_processes(name):
    processes = subprocess.Popen('ps ax | grep "%s" | grep -v grep' % name,
        shell=True, stdout=subprocess.PIPE)
    processes, _ = processes.communicate()
    targets = []
    for process in processes.split('\n')[:-1]:
        targets.append(process.lstrip().split(' ')[0])
    return targets


def start(arguments, config, work_data):
    if arguments.target in ('server', 'all'):
        servers = find_matching_processes('python %s' %
            work_data['trytond_exec'])
        if servers:
            print 'Server is already up and running !'
        else:
            base_line = [work_data['python_exec'], work_data['trytond_exec'],
                '-c', work_data['trytond_conf']]
            if arguments.mode == 'dev':
                base_line += ['--dev']
            elif arguments.mode == 'debug':
                base_line += ['--dev', '--verbose']
            try:
                server_process = subprocess.Popen(base_line + ['-s',
                        config.get('parameters', 'sentry_dsn')])
            except ConfigParser.NoOptionError:
                server_process = subprocess.Popen(base_line)
            print 'Server started, pid %s' % server_process.pid
    if arguments.target in ('client', 'all'):
        if arguments.mode == 'demo':
            subprocess.Popen([work_data['python_exec'],
                    work_data['tryton_exec'], '-c', work_data['tryton_conf']])
        elif arguments.mode == 'dev':
            subprocess.Popen([work_data['python_exec'],
                    work_data['tryton_exec'], '-c', work_data['tryton_conf'],
                    '-d'])
        elif arguments.mode == 'debug':
            subprocess.Popen([work_data['python_exec'],
                    work_data['tryton_exec'], '-c', work_data['tryton_conf'],
                    '-l', 'DEBUG', '-d', '-v'])


def kill(arguments, config, work_data):
    if arguments.target in ('server', 'all'):
        servers = find_matching_processes('python %s' %
            work_data['trytond_exec'])
        if not servers:
            print 'Server is already down !'
        else:
            result = subprocess.Popen(['kill', '-9'] + servers)
            result.communicate()
    if arguments.target in ('client', 'all'):
        clients = find_matching_processes('python %s ' %
            work_data['tryton_exec'])
        if not clients:
            print 'No client found running !'
        else:
            result = subprocess.Popen(['kill', '-9'] + clients)
            result.communicate()


def sync(arguments, config, work_data):
    def sync_this(repo_name):
        repo_path = os.path.join(work_data['runtime_dir'], repo_name)
        os.chdir(repo_path)
        os.system('hg pull -u')

    if arguments.target in ('server', 'all'):
        sync_this('trytond')
    if arguments.target in ('client', 'all'):
        sync_this('tryton')
    if arguments.target in ('proteus', 'all'):
        sync_this('proteus')
    if arguments.target in ('coop', 'all'):
        sync_this('coopbusiness')
        arguments.env = os.environ['VIRTUAL_ENV']
        configure(arguments.env)


def database(arguments, config, work_data):
    if arguments.action == 'drop':
        os.system('sudo su postgres -c "dropdb %s"' % arguments.database)
    elif arguments.action == 'install':
        subprocess.Popen([work_data['trytond_exec'], '-d', arguments.database,
                '-c', work_data['trytond_conf'], '--init', arguments.module])
    elif arguments.action == 'update':
        subprocess.Popen([work_data['trytond_exec'], '-d', arguments.database,
                '-c', work_data['trytond_conf'], '--update', arguments.module])
    elif arguments.action == 'test_case':
        command_line = [work_data['python_exec'],
            work_data['tryton_script_launcher'], os.path.join(
                work_data['runtime_dir'], 'coopbusiness', 'test_case',
                'proteus_test_case.py'), arguments.database]
        if arguments.test_case == 'all':
            process = subprocess.Popen(command_line)
        else:
            process = subprocess.Popen(command_line, arguments.test_case)
        process.communicate()


def test(arguments, config, work_data):
    import logging
    import datetime
    import threading
    import multiprocessing
    import time

    def set_logger():
        log_dir = os.path.join(work_data['runtime_dir'], 'test_log')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            os.makedirs(os.path.join(log_dir, 'test_results'))
        else:
            for file in os.listdir(log_dir):
                if file != 'test_results':
                    os.remove(os.path.join(log_dir, file))
            if not os.path.exists(os.path.join(log_dir, 'test_results')):
                os.makedirs(os.path.join(log_dir, 'test_results'))

        logFormatter = logging.Formatter('[%(asctime)s] %(levelname)s:'
            '%(name)s: %(message)s', '%a %b %d %H:%M:%S %Y')
        testLogger = logging.getLogger('unittest')
        testLogger.setLevel(logging.INFO)

        fileHandler = logging.FileHandler(os.path.join(log_dir,
                'test_results', datetime.datetime.now().strftime(
                    '%Y-%m-%d_%Hh%Mm%Ss') + '_test_execution.log'))
        fileHandler.setFormatter(logFormatter)
        testLogger.addHandler(fileHandler)

        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        testLogger.addHandler(consoleHandler)
        return log_dir

    def test_module(module, module_dir, log_folder, base_command_line):
        if not (os.path.isdir(os.path.join(module_dir, module))
                and os.path.isfile(os.path.join(module_dir, module,
                        'tryton.cfg'))):
            return
        if os.path.isdir(os.path.join(module_dir, module, 'tests')):
            logfile = os.path.join(log_folder, module + '.test_log')
            try:
                os.remove(logfile)
            except:
                pass
            logfile_desc = os.open(logfile, os.O_RDWR | os.O_CREAT)
            logfile = os.fdopen(logfile_desc, 'w')
            logging.getLogger('unittest').info('Launching unittest for '
                'module  %s' % module)
            test = subprocess.Popen(base_command_line + [module],
                stdout=logfile, stderr=logfile)
            test.communicate()
            logfile.close()

    def format_result(log_dir):
        file_names = os.listdir(log_dir)
        file_names.sort()
        log_files = map(lambda x: os.path.join(log_dir, x), file_names)
        summary = {}
        for file in log_files:
            if os.path.isdir(file):
                continue
            cur_module = file.rsplit('/', 1)[1].split('.')[0]
            sum = {}
            lines = open(file).readlines()
            if lines[-1][:-1] == 'OK':
                sum['errors'] = 0
            elif lines[-1][:6] == 'FAILED':
                sum['errors'] = 0
                if lines[-1][8] == 'f':
                    fail = lines[-1].split('failures=')[1]
                    if len(fail) > 3:
                        sum['errors'] += int(fail.split(',')[0])
                        sum['errors'] += int(fail.split('errors=')[1][:-2])
                    else:
                        sum['errors'] += int(fail[:-2])
                else:
                    sum['errors'] = int(lines[-1][15:-2])
            else:
                sum['errors'] = 0

            if lines[-1][:-1] != 'OK':
                logging.getLogger('unittest').info('=' * 80)
                logging.getLogger('unittest').info('Test results (detailed) '
                    'for module ' + cur_module)
                logging.getLogger('unittest').info('=' * 80)
                for line in lines:
                    logging.getLogger('unittest').info(line[:-1])

            try:
                sum['number'] = int(lines[-3].split(' ', 2)[1])
            except:
                sum['number'] = 1

            try:
                sum['time'] = float(lines[-3][:-1].rsplit(' ', 1)[1][:-1])
            except:
                sum['time'] = 0

            summary[cur_module] = sum

        logging.getLogger('unittest').info('=' * 80)
        logging.getLogger('unittest').info('Global summary')
        logging.getLogger('unittest').info('=' * 80)
        final = {'number': 0, 'time': 0.00, 'errors': 0}

        tag = False
        for key, value in summary.iteritems():
            if not tag:
                logging.getLogger('unittest').info('=' * 80)
                logging.getLogger('unittest').info('PASSED :')
                logging.getLogger('unittest').info('=' * 80)
                tag = True
            if value['errors'] == 0:
                logging.getLogger('unittest').info('Module %s ran %s tests '
                    'in %s seconds' % (key, value['number'], value['time']))
                for key1, value1 in value.iteritems():
                    final[key1] += value1

        tag = False
        for key, value in summary.iteritems():
            if value['errors'] != 0:
                if not tag:
                    logging.getLogger('unittest').info('=' * 80)
                    logging.getLogger('unittest').info('FAILED :')
                    logging.getLogger('unittest').info('=' * 80)
                    tag = True
                logging.getLogger('unittest').info('Module %s ran %s tests '
                    'in %s seconds with %s failures' % (
                        key, value['number'], value['time'], value['errors']))
                for key1, value1 in value.iteritems():
                    final[key1] += value1

        logging.getLogger('unittest').info('')
        logging.getLogger('unittest').info('Total : %s tests in %.2f seconds '
            'with %s failures' % (final['number'], final['time'],
                final['errors']))

    if arguments.database:
        base_command_line = ['env', 'DB_NAME=%s' % arguments.database]
    else:
        base_command_line = ['env']
    if not arguments.with_test_cases:
        base_command_line.append('DO_NOT_TEST_CASES=True')
    base_command_line.extend([work_data['trytond_test_runner'], '-c',
            work_data['tests_conf'], '-m'])
    argument_list = arguments.module
    if argument_list == 'all':
        argument_list = os.listdir(work_data['coop_modules'])
        # TODO : Improve ordering
        # Currently, we use the fact that pop takes the last element of the
        # alphabetically ordered list to make sure test_module is run asap to
        # better leverage multiprocessing.
        # In the future, we would need to have a consistent way to make heavy
        # test modules like test_module be tested first.
        argument_list.sort()

    num_processes = multiprocessing.cpu_count()
    threads = []
    log_dir = set_logger()

    # run until all the threads are done, and there is no data left
    while threads or argument_list:
        if (len(threads) < num_processes) and argument_list:
            t = threading.Thread(
                target=test_module, args=[argument_list.pop(),
                    work_data['modules'],
                    log_dir, base_command_line])
            t.setDaemon(True)
            time.sleep(1)
            t.start()
            threads.append(t)
        else:
            time.sleep(1)
            for thread in threads:
                if not thread.isAlive():
                    threads.remove(thread)

    # Delete test databases if needed
    if arguments.delete_test_databases:
        try:
            db_user = config.get('parameters', 'test_postgres_user')
        except:
            db_user = 'postgres'
        try:
            db_password = config.get('parameters', 'test_postgres_password')
        except:
            db_password = 'postgres'
        dbs = subprocess.Popen('PGPASSWORD=%s psql -l -U %s | '
            'grep \'test_1\' | cut -f2 -d \' \';' % (db_password, db_user),
            shell=True, stdout=subprocess.PIPE)
        databases, errs = dbs.communicate()
        for elem in databases.split('\n'):
            killer = subprocess.Popen('PGPASSWORD=%s dropdb %s -U %s' %
                (db_password, elem, db_user), shell=True)
            killer.communicate()
    format_result(log_dir)


def batch(arguments, config, work_data):
    if arguments.action == 'kill':
        workers = find_matching_processes('celery')
        if not workers:
            print 'No celery process found'
        else:
            result = subprocess.Popen(['kill', '-9'] + workers)
            result.communicate()
    elif arguments.action == 'execute':
        import time
        log_path = os.path.join(work_data['runtime_dir'], 'logs',
            arguments.name + '.log'),
        subprocess.Popen('celery worker -l info '
            '--config=celeryconfig '
            '--app=trytond.modules.cog_utils.batch_launcher'
            ' --logfile=%s' % log_path, shell=True, stdout=subprocess.PIPE)
        time.sleep(2)
        _execution = subprocess.Popen('celery call '
            'trytond.modules.cog_utils.batch_launcher.generate_all '
            '--args=\'["%s", "%s", "%s"]\'' % (arguments.name,
                arguments.connexion_date, arguments.treatment_date),
            shell=True, stdout=subprocess.PIPE)
        _execution.communicate()
        print 'See log at %s' % log_path


def export(arguments, config, work_data):
    if arguments.target == 'translations':
        if arguments.module == 'all':
            process = subprocess.Popen(['env', 'DB_NAME=%s' %
                    arguments.database, work_data['python_exec'],
                    work_data['tryton_script_launcher'], os.path.join(
                        work_data['runtime_dir'], 'coopbusiness', 'test_case',
                        'export_translations.py')])
        else:
            process = subprocess.Popen(['env', 'DB_NAME=%s' %
                    arguments.database, work_data['python_exec'],
                    work_data['tryton_script_launcher'], os.path.join(
                        work_data['runtime_dir'], 'coopbusiness', 'test_case',
                        'export_translations.py')] + arguments.module)
        process.communicate()


def create_symlinks(modules_path, lang, root, remove=True):
    import glob

    # TODO : called symlinks.py available in trydoc
    if remove:
        # Removing existing symlinks
        for root_file in os.listdir(root):
            if os.path.islink(root_file):
                print "removing %s" % root_file
                os.remove(root_file)

    for module_doc_dir in glob.glob('%s/*/doc/%s' % (modules_path, lang)):
        print "symlink to %s" % module_doc_dir
        module_name_dir = os.path.dirname(os.path.dirname(module_doc_dir))
        module_name = os.path.basename(module_name_dir)
        print "module name %s" % module_name
        symlink = os.path.join(root, module_name)
        if not os.path.exists(symlink):
            os.symlink(module_doc_dir, symlink)

    rootIndex = os.path.join(root, 'index.rst')
    if os.path.exists(rootIndex):
        os.remove(rootIndex)
    indexFileName = os.path.join(modules_path, 'index_' + lang + '.rst')
    if os.path.exists(indexFileName):
        os.symlink(indexFileName, rootIndex)


def documentation(arguments, config, work_data):
    from sphinxcontrib import trydoc

    doc_files = os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
        'doc_files')
    if arguments.initialize:
        if not os.path.exists(doc_files):
            os.makedirs(doc_files)
        trydocdir = os.path.dirname(trydoc.__file__)
        if not os.path.exists(os.path.join(trydocdir,
                'index.rst.' + arguments.language + '.template')):
            shutil.copyfile(os.path.join(trydocdir, 'index.rst.fr.template'),
                os.path.join(trydocdir, 'index.rst.' + arguments.language +
                    '.template'))
        process = subprocess.Popen(['sphinx-quickstart', doc_files])
        process.communicate()
    elif arguments.generate:
        create_symlinks(os.path.join(os.environ['VIRTUAL_ENV'],
            'tryton-workspace', 'coopbusiness', 'doc'), arguments.language,
            doc_files, True)
        process = subprocess.Popen(['make', arguments.format],
            cwd=doc_files)
        process.communicate()


def configure(target_env):
    import proteus

    root = os.path.normpath(os.path.abspath(target_env))
    base_name = os.path.basename(root)
    workspace = os.path.join(root, 'tryton-workspace')
    coopbusiness = os.path.join(workspace, 'coopbusiness')
    os.chdir(os.path.join(root, 'bin'))
    process = subprocess.Popen(['ln', '-s', os.path.join(coopbusiness,
            'scripts', 'script_launcher.py'), 'coop'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    module_dir = os.path.join(workspace, 'coopbusiness', 'modules')
    for elem in os.listdir(module_dir):
        if not os.path.isdir(os.path.join(module_dir, elem)):
            continue
        if not os.path.exists(os.path.join(module_dir, elem, '__init__.py')):
            shutil.rmtree(os.path.join(module_dir, elem))
    os.chdir(os.path.join(workspace, 'coopbusiness'))
    os.system('find . -name "*.pyc" -exec rm -rf {} \;')
    os.system('find . -name "*.rej" -exec rm -rf {} \;')
    os.system('find . -name "*.orig" -exec rm -rf {} \;')
    os.chdir(os.path.join(workspace, 'trytond', 'trytond', 'modules'))
    for filename in os.listdir(os.path.join(workspace, 'trytond', 'trytond',
                'modules')):
        target = os.path.join(workspace, 'trytond', 'trytond', 'modules',
            filename)
        if not os.path.islink(target):
            continue
        os.unlink(target)
    os.system('ln -s ../../../coopbusiness/modules/* . 2> /dev/null')
    if not os.path.exists(os.path.join(workspace, 'logs')):
        os.makedirs(os.path.join(workspace, 'logs'))
    if not os.path.exists(os.path.join(workspace, 'conf')):
        os.makedirs(os.path.join(workspace, 'conf'))
    if not os.path.exists(os.path.join(workspace, 'conf', 'py_scripts.conf')):
        with open(os.path.join(workspace, 'conf', 'py_scripts.conf'),
                'w') as f:
            f.write('\n'.join([
                        '[parameters]',
                        'db_name = %s' % base_name,
                        'start_mode = demo',
                        'runtime_dir = tryton-workspace']))
    if not os.path.exists(os.path.join(workspace, 'conf', 'trytond.conf')):
        with open(os.path.join(workspace, 'conf', 'trytond.conf'), 'w') as f:
            f.write('\n'.join([
                        '[jsonrpc]',
                        'listen = localhost:8000\n',
                        '[database]',
                        'uri = postgresql://tryton:tryton@localhost:5432/',
                        'path = %s\n' % os.path.join(workspace, 'data'),
                        '[session]',
                        'super_pwd = zqpVUjCebLpr6',
                        '# default password is admin',
                        ]))
    if not os.path.exists(os.path.join(workspace, 'conf', 'tests.conf')):
        with open(os.path.join(workspace, 'conf', 'tests.conf'), 'w') as f:
            f.write('\n'.join([
                        '[jsonrpc]',
                        'listen = localhost:8000\n',
                        '[database]',
                        'db_type = sqlite',
                        'uri = sqlite://',
                        'path = %s\n' % os.path.join(workspace, 'data'),
                        '[env]',
                        'testing = True',
                        ]))
    if not os.path.exists(os.path.join(workspace, 'conf', 'celeryconfig.py')):
        with open(os.path.join(workspace, 'conf', 'celeryconfig.py'),
                'w') as f:
            f.write('\n'.join([
                        "BROKER_URL = 'amqp://guest:guest@localhost:5672//'",
                        'CELERYD_CONCURRENCY = 4',
                        'CELERY_REDIRECT_STDOUT = False',
                        'CELERYD_TASK_LOG_FORMAT = '
                        "'[%(asctime)s: %(levelname)s/%(processName)s]"
                        "[%(task_name)s] %(message)s'",
                        "TRYTON_DATABASE = '%s'" % base_name,
                        "CELERY_ACCEPT_CONTENT = ['pickle', 'json']",
                        "TRYTON_CONFIG = '%s'" % os.path.join(workspace,
                            'conf', 'trytond.conf')]))
    if not os.path.exists(os.path.join(workspace, 'conf', 'tryton.conf')):
        with open(os.path.join(workspace, 'conf', 'tryton.conf'), 'w') as f:
            f.write('\n'.join([
                        '[login]',
                        'login = admin',
                        'profile = Test',
                        'expanded = True',
                        'port = 8000',
                        'server = localhost',
                        'db = %s' % base_name,
                        '',
                        '[client]',
                        'save_tree_expanded_state = True',
                        'default_height = 800',
                        'language_direction = ltr',
                        'form_tab = top',
                        'lang = fr_FR',
                        'modepda = False',
                        'save_tree_state = True',
                        'toolbar = default',
                        'default_width = 1280',
                        'save_width_height = True',
                        'maximize = True',
                        '',
                        '[menu]',
                        'pane = 220',
                        'expanded = True',
                        '',
                        '[form]',
                        'statusbar = True']))
    # configure documentation
    proteusdir = os.path.dirname(proteus.__file__)
    if not os.path.islink(proteusdir):
        shutil.rmtree(proteusdir)
        os.symlink(os.path.join(workspace, 'proteus', 'proteus'), proteusdir)

    def path_inserter(target, filename):
        target_file = os.path.join(root, 'lib', 'python2.7', 'site-packages',
            filename + '.pth')
        if not os.path.exists(target_file):
            with open(target_file, 'w') as f:
                f.write('\n'.join([
                            'import sys; sys.__plen = len(sys.path)',
                            '%s' % target,
                            'import sys; new=sys.path[sys.__plen:]',
                            'del sys.path[sys.__plen:]',
                            "p=getattr(sys,'__egginsert',0)",
                            'sys.path[p:p]=new',
                            'sys.__egginsert = p+len(new)']))

    path_inserter(os.path.join(workspace, 'trytond'), '_trytond_path')
    path_inserter(os.path.join(workspace, 'tryton'), '_tryton_path')
    path_inserter(os.path.join(workspace, 'proteus'), '_proteus_path')
    path_inserter(os.path.join(workspace, 'conf'), '_celery_conf_path')
    path_inserter(os.path.join(workspace, 'coopbusiness', 'trytond_celery'),
        '_trytond_celery_path')


if __name__ == '__main__':
    if 'VIRTUAL_ENV' not in os.environ:
        target = os.path.join(DIR, '..', '..', '..', 'bin', 'activate_this.py')
        execfile(target, dict(__file__=target))
        os.environ['VIRTUAL_ENV'] = os.path.abspath(os.path.join(target, '..',
                '..'))

    config = ConfigParser.ConfigParser()
    try:
        with open(os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
                    'conf', 'py_scripts.conf'), 'r') as fconf:
                config.readfp(fconf)
    except:
        configure(os.environ['VIRTUAL_ENV'])
        with open(os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
                    'conf', 'py_scripts.conf'), 'r') as fconf:
                config.readfp(fconf)

    work_data = init_work_data(config)
    possible_modules = os.listdir(work_data['modules']) + ['ir']
    possible_modules.remove('__init__.py')
    possible_coop_modules = os.listdir(work_data['coop_modules']) + ['all']

    # Main parser
    parser = argparse.ArgumentParser(description='Launch utilitary scripts')
    subparsers = parser.add_subparsers(title='Subcommands',
        description='Valid subcommands', dest='command')

    # Start parser
    parser_start = subparsers.add_parser('start',
        help='start client / server')
    parser_start.add_argument('target', choices=['server', 'client',
            'all'], help='What should be started')
    parser_start.add_argument('--mode', '-m', choices=['demo', 'dev',
            'debug'], default=config.get('parameters', 'start_mode'))

    # Batch parser
    parser_batch = subparsers.add_parser('batch', help='Launches a batch')
    parser_batch.add_argument('action', choices=['kill', 'execute'])
    parser_batch.add_argument('--name', type=str, help='Name of the batch'
        'to launch')
    parser_batch.add_argument('--connexion-date', '-c', type=str,
        help='Date used to log in',
        default=datetime.date.today().isoformat())
    parser_batch.add_argument('--treatment-date', '-t', type=str,
        help='Batch treatment date',
        default=datetime.date.today().isoformat())

    # Database parser
    parser_database = subparsers.add_parser('database', help='Execute a '
        'database action')
    parser_database.add_argument('action', choices=['update', 'install',
            'drop', 'test_case'], help='The action to take on the database')
    parser_database.add_argument('--database', '-d', help='Database name',
        default=config.get('parameters', 'db_name'), type=str)
    parser_database.add_argument('--module', '-m',
        help='Module name {account,account_aggregate,etc...}',
        default='ir', type=str, choices=possible_modules,
        metavar='MODULE_NAME')
    parser_database.add_argument('--test-case', '-t', help='Test case to run',
        default='all')

    # Kill parser
    parser_kill = subparsers.add_parser('kill', help='Kills running tryton '
        'processes')
    parser_kill.add_argument('target', choices=['server', 'client',
            'all'], help='What should be killed')

    # Sync parser
    parser_sync = subparsers.add_parser('sync',
        help='Sync current environment')
    parser_sync.add_argument('target', choices=['client', 'server', 'proteus',
            'coop', 'all'], default='all')

    # Test parser
    parser_unittests = subparsers.add_parser('test', help='Test related '
        'actions')
    parser_unittests.add_argument('--module', '-m', default='all',
        help='Module to unittest {account,account_aggregate,etc...}',
        nargs='+', choices=possible_modules, metavar='MODULE_NAME')
    parser_unittests.add_argument('--database', '-d', help='Database name',
        default='', type=str)
    parser_unittests.add_argument('--with-test-cases', '-t', help='Allow test '
        'cases execution as unittests', action='store_true')
    parser_unittests.add_argument('--delete-test-databases', '-k',
        help='Delete test databases after execution', action='store_true')

    # Export parser
    parser_export = subparsers.add_parser('export', help='Export various '
        'things')
    parser_export.add_argument('target', choices=['translations'],
        help='What to export')
    parser_export.add_argument('--database', '-d', help='Database name',
        default=config.get('parameters', 'db_name'), type=str)
    parser_export.add_argument('--module', '-m', default='all',
        help='Module to export {account,account_aggregate,etc...}',
        nargs='+', choices=possible_coop_modules, metavar='MODULE_NAME')

    # Configure parser
    parser_configure = subparsers.add_parser('configure', help='Configure '
        'directory')
    parser_configure.add_argument('--env', '-e', help='Root of environment '
        'to configure', default=os.environ['VIRTUAL_ENV'])

    # Doc parser
    parser_doc = subparsers.add_parser('doc', help='Generate documentation')
    parser_doc.add_argument('--database', '-d', help='Define the '
        'database to used',
        default=os.path.basename(os.environ['VIRTUAL_ENV']))
    parser_doc.add_argument('--language', '-l', help='Documentation language',
        default='fr')
    parser_doc.add_argument('--generate', '-g', help='Generate the '
        'documentation', action='store_true')
    parser_doc.add_argument('--initialize', '-i', help='Launch the '
        'tyrdoc quickstart process', action='store_true')
    parser_doc.add_argument('--format', '-f', help='format for documentation '
        'generation : html, ...', default='html')

    argcomplete.autocomplete(parser)
    arguments = parser.parse_args()

    if arguments.command == 'start':
        start(arguments, config, work_data)
    elif arguments.command == 'kill':
        kill(arguments, config, work_data)
    elif arguments.command == 'sync':
        sync(arguments, config, work_data)
    elif arguments.command == 'database':
        database(arguments, config, work_data)
    elif arguments.command == 'test':
        test(arguments, config, work_data)
    elif arguments.command == 'batch':
        batch(arguments, config, work_data)
    elif arguments.command == 'export':
        export(arguments, config, work_data)
    elif arguments.command == 'configure':
        configure(arguments.env)
    elif arguments.command == 'doc':
        documentation(arguments, config, work_data)

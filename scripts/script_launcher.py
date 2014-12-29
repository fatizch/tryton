#!/usr/bin/env python
# encoding: utf-8
# PYTHON_ARGCOMPLETE_OK
import datetime
import glob
import os
import shutil
import subprocess
import time

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


def get_batch_names(modules_dirpath):
    out = subprocess.check_output(
        "grep -R -A9 --include='batch.py' -e 'class.*BatchRoot.*):' %s"
        % modules_dirpath, shell=True)
    return [l.split('=')[1].strip("' ")
        for l in out.split('\n') if '__name__ =' in l]


def start(arguments, config, work_data):
    if arguments.target in ('server', 'all'):
        servers = find_matching_processes('python %s' %
            work_data['trytond_exec'])
        if servers:
            print 'Server is already up and running !'
        else:
            base_line = [work_data['python_exec'], work_data['trytond_exec'],
                '-c', work_data['trytond_conf']]
            if arguments.cron:
                base_line += ['--cron']
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
    def sync_this(repo_name, branch_name='default'):
        repo_path = os.path.join(work_data['runtime_dir'], repo_name)
        os.chdir(repo_path)
        if arguments.insecure:
            os.system('hg pull --insecure')
        else:
            os.system('hg pull')
        os.system('hg update %s' % branch_name)

    if arguments.target in ('server', 'all'):
        sync_this('trytond', 'dev')
    if arguments.target in ('client', 'all'):
        sync_this('tryton', 'coopengo')
    if arguments.target in ('proteus', 'all'):
        sync_this('proteus')
    if arguments.target in ('coop', 'all'):
        sync_this('coopbusiness')
        arguments.env = os.environ['VIRTUAL_ENV']
        configure(arguments.env)


def database(arguments, config, work_data):
    if arguments.action == 'drop':
        cmd = 'sudo su postgres -c "dropdb %s"' % arguments.database
    elif arguments.action == 'install':
        cmd = [work_data['trytond_exec'], '-d', arguments.database,
            '-c', work_data['trytond_conf'], '--init', arguments.module]
    elif arguments.action == 'update':
        cmd = [work_data['trytond_exec'], '-d', arguments.database,
            '-c', work_data['trytond_conf'], '--update', arguments.module]
    elif arguments.action == 'test_case':
        cmd = [work_data['python_exec'], work_data['tryton_script_launcher'],
            os.path.join(work_data['runtime_dir'], 'coopbusiness', 'test_case',
                'proteus_test_case.py'), arguments.database]
        if arguments.test_case != 'all':
            cmd += arguments.test_case
    return subprocess.call(cmd)


def test(arguments, config, work_data):
    import logging
    import datetime
    import threading
    import multiprocessing

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
    if not arguments.keep_test_databases:
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
    import celery
    from celery.result import GroupResult
    from trytond.modules.cog_utils import batch_launcher

    log_path = os.path.join(work_data['runtime_dir'], 'logs',
        'celery_batch.log')
    APPNAME = 'trytond.modules.cog_utils.batch_launcher'
    PING_ATTEMPTS_DELAY = (10, .3)
    if arguments.action == 'init':
        workers = find_matching_processes('celery')
        if workers:
            subprocess.call(['kill', '-9'] + workers)
            print 'Running workers killed.'
        cmd = ['celery', 'worker', '-l', 'info',
            '--config=celeryconfig', '--app=%s' % APPNAME,
            '--logfile=%s' % log_path]
        with open(os.devnull, 'w') as fnull:
            subprocess.Popen(' '.join(cmd), shell=True, stdout=fnull,
                stderr=subprocess.STDOUT)
        for i in range(PING_ATTEMPTS_DELAY[0]):
            if celery.current_app.control.inspect().ping():
                print 'Workers started, see %s' % log_path
                return 0
            time.sleep(PING_ATTEMPTS_DELAY[1])
        print 'Failed starting worker instance'
        return 1
    elif arguments.action == 'execute':
        if not celery.current_app.control.inspect().ping():
            print 'No celery worker found. Run `coop batch init` first.'
            return 1
        else:
            status = batch_launcher.generate_all.delay(arguments.name,
                arguments.connexion_date, arguments.treatment_date)
            for s in status.collect():
                if isinstance(s[0], (GroupResult, tuple)):
                    result, vals = s
                    if any(vals):
                        return 1
    elif arguments.action == 'monitor':
        with open(os.devnull, 'w') as fnull:
            subprocess.Popen(['celery', '--app=%s' % APPNAME,
                        'flower'], stdout=fnull, stderr=subprocess.STDOUT)
            print 'Celery monitoring web server available at localhost:5555'
    return 0


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


def doc(arguments=None, config=None, work_data=None, override_values=None):
    override_values = override_values or {}
    doc_files = override_values.get('doc_files', None) or (
        os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
            'doc_files'))
    documentation_dir = os.path.join(override_values.get('repo',
            None) or os.path.join(work_data['runtime_dir'], 'coopbusiness'),
        'documentation')
    modules = os.path.join(override_values.get('repo', None) or
        os.path.join(work_data['runtime_dir'], 'coopbusiness'),
        'modules')
    language = override_values.get('lang', None) or arguments.language
    format = override_values.get('format', None) or arguments.format

    # Clean up previous build
    if os.path.exists(doc_files):
        shutil.rmtree(doc_files)
    shutil.copytree(documentation_dir, doc_files)

    # Populate build folder
    for module_doc_dir in glob.glob(os.path.join(modules,
                '*', 'doc', language)):
        module_name = os.path.basename(os.path.dirname(os.path.dirname(
                    module_doc_dir)))
        sym_link = os.path.join(doc_files, module_name)
        os.symlink(module_doc_dir, sym_link)
    shutil.copyfile(os.path.join(doc_files, 'index_%s.rst' % language),
        os.path.join(doc_files, 'index.rst'))

    # Generate the doc
    process = subprocess.Popen(['make', format], cwd=doc_files)
    process.communicate()


def configure(target_env):
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
    conf_files = [os.path.join(workspace, 'conf', cfg)
        for cfg in ['trytond.conf', 'tests.conf', 'celeryconfig.py',
            'tryton.conf']]
    template_vals = dict(
        WORKSPACE=workspace,
        DATABASE=base_name,
    )
    for fname in conf_files:
        if not os.path.exists(fname):
            with open(fname, 'w') as f, \
                    open(os.path.join(workspace, 'coopbusiness', 'defaults',
                            os.path.basename(fname))) as template:
                data = template.read()
                for key in template_vals.keys():
                    placeholder = '$' + key
                    if placeholder in data:
                        data = data.replace(placeholder, template_vals[key])
                f.write(data)

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


if __name__ == '__main__':
    if 'VIRTUAL_ENV' not in os.environ:
        target = os.path.join(DIR, '..', '..', '..', 'bin', 'activate_this.py')
        execfile(target, dict(__file__=target))
        os.environ['VIRTUAL_ENV'] = os.path.abspath(os.path.join(target, '..',
                '..'))

    import ConfigParser
    import argparse
    import argcomplete
    from argparse import RawTextHelpFormatter

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

    def get_subdirectories(dirpath):
        return [d for d in os.listdir(dirpath)
            if os.path.isdir(os.path.join(dirpath, d))]

    possible_modules = sorted(get_subdirectories(work_data['modules']) +
        ['ir'])
    possible_coop_modules = ['all'] + sorted(get_subdirectories(
        work_data['coop_modules']))

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
    parser_start.add_argument('--cron', help='Launch the server with cron'
        ' functionality', action='store_true')

    # Batch parser
    usage_str = \
"""Examples:
  Restart celery workers pool: coop batch init
  Enter an unknown name to list available batches: coop batch --name ???
  Run a batch: coop batch execute --name account.payment.creation -t 2015-01-01
    """
    action_str = \
"""init   : kill running celery workers and start a new pool of workers.
execute: run a batch. REQUIRES: --name
monitor: starts celery flower server on http://localhost:5555"""
    help_str = ('Interacts with coop batch environment based on celery '
 '<http://www.celeryproject.org/>')
    parser_batch = subparsers.add_parser('batch',
        description=help_str,
        epilog=usage_str, formatter_class=RawTextHelpFormatter)
    parser_batch.add_argument('action', choices=['init', 'execute', 'monitor'],
        help=action_str)
    parser_batch.add_argument('--name', type=str, help='Name of the batch to'
        'launch', choices=sorted(get_batch_names(work_data['modules'])),
         metavar='BATCH_NAME')
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
    parser_sync.add_argument('--insecure', '-i', help='Allow https connections'
        ' to self-signed certificates', action='store_true')

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
    parser_unittests.add_argument('--keep-test-databases', '-k',
        help='Keep test databases after execution', action='store_true')

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
    parser_doc.add_argument('--language', '-l', help='Documentation language',
        default='fr')
    parser_doc.add_argument('--format', '-f', help='format for documentation '
        'generation : html, ...', default='html')

    argcomplete.autocomplete(parser)
    arguments = parser.parse_args()

    if arguments.command == 'configure':
        configure(arguments.env)
    else:
        status = globals()[arguments.command](arguments, config, work_data)
        exit(status or 0)

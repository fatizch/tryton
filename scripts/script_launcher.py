#!/usr/bin/env python
# encoding: utf-8
import shutil
import os
import ConfigParser
import argparse
import subprocess

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))

POSSIBLE_ACTIONS = [
    'launch_server',
    'launch',
    'launch_client',
    ]


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
    result['tryton_script_launcher'] = os.path.join(result['runtime_dir'],
        'coopbusiness', 'scripts', 'python_scripts', 'launch_tryton_script.py')
    return result


def find_matching_processes(name):
    processes = subprocess.Popen('ps ax | grep "%s" | grep -v grep' % name,
        shell=True, stdout=subprocess.PIPE)
    processes, _ = processes.communicate()
    targets = []
    for process in processes.split('\n')[:-1]:
        targets.append(process.lstrip().split(' ')[0])
    return targets


def launch(arguments, config, work_data):
    if arguments.target in ('server', 'all'):
        servers = find_matching_processes('python %s' %
            work_data['trytond_exec'])
        if servers:
            print 'Server is already up and running !'
        else:
            server_process = subprocess.Popen([work_data['python_exec'],
                    work_data['trytond_exec'], '-c',
                    work_data['trytond_conf']])
            print 'Server launched, pid %s' % server_process.pid
    if arguments.target in ('client', 'all'):
        subprocess.Popen([work_data['python_exec'], work_data['tryton_exec'],
                '-c', work_data['tryton_conf']])


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
        configure(arguments, config, work_data)


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
                'proteus_test_case.py')]
        if arguments.test_case == 'all':
            process = subprocess.Popen(command_line)
        else:
            process = subprocess.Popen(command_line, arguments.test_case)
        process.communicate()


def test(arguments, config, work_data):
    base_command_line = [] if arguments.with_test_cases else ['env',
        'DO_NOT_TEST_CASES=True']
    base_command_line += [work_data['python_exec'],
        work_data['tryton_script_launcher']]
    if arguments.module == 'all':
        test_process = subprocess.Popen(base_command_line + [os.path.join(
                    work_data['runtime_dir'], 'coopbusiness', 'test_case',
                    'launch_all_tests.py')])
    else:
        test_process = subprocess.Popen(base_command_line + [os.path.join(
                    work_data['runtime_dir'], 'coopbusiness', 'modules',
                    arguments.module, 'tests', 'test_module.py')])
    test_process.communicate()


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
            '--app=trytond.modules.coop_utils.batch_launcher'
            ' --logfile=%s' % log_path, shell=True, stdout=subprocess.PIPE)
        time.sleep(2)
        _execution = subprocess.Popen('celery call '
            'trytond.modules.coop_utils.batch_launcher.generate_all '
            '--args=\'["%s"]\'' % arguments.name, shell=True,
            stdout=subprocess.PIPE)
        _execution.communicate()
        print 'See log at %s' % log_path


def export(arguments, config, work_data):
    if arguments.target == 'translations':
        process = subprocess.Popen([work_data['python_exec'],
            work_data['tryton_script_launcher'], os.path.join(
                        work_data['runtime_dir'], 'coopbusiness', 'test_case',
                        'export_translations.py')])
        process.communicate()


def configure(arguments, config, work_data):
    root = os.path.normpath(os.path.abspath(arguments.env))
    base_name = os.path.basename(root)
    workspace = os.path.join(root, 'tryton-workspace')
    coopbusiness = os.path.join(workspace, 'coopbusiness')
    os.chdir(os.path.join(root, 'bin'))
    process = subprocess.Popen(['ln', '-s', os.path.join(coopbusiness,
            'scripts', 'script_launcher.py'), 'coop_start'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    module_dir = os.path.join(workspace, 'coopbusiness', 'modules')
    for elem in os.listdir(module_dir):
        if not os.path.isdir(os.path.join(module_dir, elem)):
            continue
        if not os.path.exists(os.path.join(module_dir, elem, '__init__.py')):
            shutil.rmtree(os.path.join(module_dir, elem))
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
                        'launch_mode = demo',
                        'runtime_dir = tryton-workspace']))
    if not os.path.exists(os.path.join(workspace, 'conf', 'trytond.conf')):
        with open(os.path.join(workspace, 'conf', 'trytond.conf'), 'w') as f:
            f.write('\n'.join([
                        '[options]',
                        'db_type = postgresql',
                        'db_user = tryton',
                        'db_password = tryton',
                        'data_path = %s' % os.path.join(workspace, 'data'),
                        'logfile = %s' % os.path.join(workspace, 'logs',
                            'server_logs.log')]))
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

    config = ConfigParser.RawConfigParser()
    with open(os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
                'conf', 'py_scripts.conf'), 'r') as fconf:
            config.readfp(fconf)

    parser = argparse.ArgumentParser(description='Launch utilitary scripts')
    subparsers = parser.add_subparsers(title='Subcommands',
        description='Valid subcommands', dest='command')
    parser_launch = subparsers.add_parser('launch',
        help='launch client / server')
    parser_launch.add_argument('target', choices=['server', 'client',
            'all'], help='What should be launched')
    parser_batch = subparsers.add_parser('batch', help='Launches a batch')
    parser_batch.add_argument('action', choices=['kill', 'execute'])
    parser_batch.add_argument('--name', type=str, help='Name of the batch'
        'to launch')
    parser_database = subparsers.add_parser('database', help='Execute a '
        'database action')
    parser_database.add_argument('action', choices=['update', 'install',
            'drop', 'test_case'], help='The action to take on the database')
    parser_database.add_argument('--database', '-d', help='Database name',
        default=config.get('parameters', 'db_name'), type=str)
    parser_database.add_argument('--module', '-m', help='Module name',
        default='all', type=str)
    parser_database.add_argument('--test-case', '-t', help='Test case to run',
        default='all')
    parser_kill = subparsers.add_parser('kill', help='Kills running tryton '
        'processes')
    parser_kill.add_argument('target', choices=['server', 'client',
            'all'], help='What should be killed')
    parser_sync = subparsers.add_parser('sync',
        help='Sync current environment')
    parser_sync.add_argument('target', choices=['client', 'server', 'proteus',
            'coop', 'all'], default='all')
    parser_unittests = subparsers.add_parser('test', help='Test related '
        'actions')
    parser_unittests.add_argument('--module', '-m', default='all',
        help='Module to unittest')
    parser_unittests.add_argument('--with-test-cases', '-t', help='Allow test '
        'cases execution as unittests', action='store_true')
    parser_export = subparsers.add_parser('export', help='Export various '
        'things')
    parser_export.add_argument('target', choices=['translations'],
        help='What to export')
    parser_configure = subparsers.add_parser('configure', help='Configure '
        'directory')
    parser_configure.add_argument('--env', '-e', help='Root of environment '
        'to configure', default=os.environ['VIRTUAL_ENV'])

    arguments = parser.parse_args()
    work_data = init_work_data(config)

    if arguments.command == 'launch':
        launch(arguments, config, work_data)
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
        configure(arguments, config, work_data)

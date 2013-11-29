import os
import logging
import subprocess
import sys
import threading
import multiprocessing
import datetime

TARGET_DIR = os.path.abspath(os.path.join(os.path.normpath(__file__),
    '..', 'test_log'))
if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR)
    os.makedirs(os.path.join(TARGET_DIR, 'test_results'))
else:
    for file in os.listdir(TARGET_DIR):
        if file != 'test_results':
            os.remove(os.path.join(TARGET_DIR, file))
    if not os.path.exists(os.path.join(TARGET_DIR, 'test_results')):
        os.makedirs(os.path.join(TARGET_DIR, 'test_results'))

logFormatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s:'
    '%(message)s', '%a %b %d %H:%M:%S %Y')
testLogger = logging.getLogger('unittest')
testLogger.setLevel(logging.INFO)

fileHandler = logging.FileHandler(os.path.join(TARGET_DIR, 'test_results',
        datetime.datetime.now().strftime('%Y-%m-%d_%Hh%Mm%Ss') +
        '_test_execution.log'))
fileHandler.setFormatter(logFormatter)
testLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
testLogger.addHandler(consoleHandler)


def test_module(module, root, log_folder):
    nb_test = 0
    if not (os.path.isdir(os.path.join(root, module))
            and os.path.isfile(os.path.join(root, module, 'tryton.cfg'))):
        return
    if os.path.isdir(os.path.join(root, module, 'tests')):
        for filename in os.listdir(os.path.join(root, module, 'tests')):
            if (not filename.startswith('test')
                    or not filename.endswith('.py')):
                continue
            nb_test += 1
            logfile = os.path.join(log_folder, module + '.test_log')
            try:
                os.remove(logfile)
            except:
                pass
            logfile_desc = os.open(logfile, os.O_RDWR | os.O_CREAT)
            logfile = os.fdopen(logfile_desc, 'w')
            logging.getLogger('unittest').info('Launching unittest for module'
                ' %s, file %s' % (module, filename))
            subprocess.call(
                [sys.executable,
                os.path.join(root, module, 'tests', filename)],
                stdout=logfile, stderr=logfile)
            logfile.close()
    if nb_test == 0:
        logging.getLogger('unittest').warning('Missing test for module %s' %
            module)


if __name__ == '__main__':
    root = os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..', 'modules'))
    modules = os.listdir(root)
    modules.sort(reverse=True)
    num_processes = multiprocessing.cpu_count()
    threads = []

    # run until all the threads are done, and there is no data left
    while threads or modules:
        if (len(threads) < num_processes) and modules:
            t = threading.Thread(
                target=test_module, args=[modules.pop(), root, TARGET_DIR])
            t.setDaemon(True)
            t.start()
            threads.append(t)
        else:
            for thread in threads:
                if not thread.isAlive():
                    threads.remove(thread)

    file_names = os.listdir(TARGET_DIR)
    file_names.sort()
    log_files = map(
        lambda x: os.path.join(TARGET_DIR, x),
        file_names)

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

    logging.getLogger('unittest').info('\n' + '=' * 80 + '\n' +
        'Global summary' + '\n' + '=' * 80)
    final = {'number': 0, 'time': 0.00, 'errors': 0}

    tag = False
    for key, value in summary.iteritems():
        if not tag:
            logging.getLogger('unittest').info('\n\tPASSED :\n')
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
                logging.getLogger('unittest').info('\n\tFAILED :\n')
                tag = True
            logging.getLogger('unittest').info('Module %s ran %s tests '
                'in %s seconds with %s failures' % (
                    key, value['number'], value['time'], value['errors']))
            for key1, value1 in value.iteritems():
                final[key1] += value1

    logging.getLogger('unittest').info('')
    logging.getLogger('unittest').info('Total : %s tests in %.2f seconds '
        'with %s failures' % (final['number'], final['time'], final['errors']))

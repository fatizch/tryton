import os
import subprocess
import sys
import threading
import multiprocessing


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
            print 'Module : %s, launching test : %s' % (module, filename)
            logfile = os.path.join(log_folder, module + '.test_log')
            try:
                os.remove(logfile)
            except:
                pass
            logfile_desc = os.open(logfile, os.O_RDWR | os.O_CREAT)
            logfile = os.fdopen(logfile_desc, 'w')
            subprocess.call(
                [sys.executable,
                os.path.join(root, module, 'tests', filename)],
                stdout=logfile, stderr=logfile)
            logfile.close()
    if nb_test == 0:
        print 'Missing test for module %s' % module


if __name__ == '__main__':
    target_dir = os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', 'test_log'))

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    else:
        for file in os.listdir(target_dir):
            os.remove(os.path.join(target_dir, file))

    root = os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..'))
    modules = os.listdir(root)
    modules.sort(reverse=True)
    num_processes = multiprocessing.cpu_count()
    threads = []

    # run until all the threads are done, and there is no data left
    while threads or modules:
        if (len(threads) < num_processes) and modules:
            t = threading.Thread(
                target=test_module, args=[modules.pop(), root, target_dir])
            t.setDaemon(True)
            t.start()
            threads.append(t)
        else:
            for thread in threads:
                if not thread.isAlive():
                    threads.remove(thread)

    file_names = os.listdir(target_dir)
    file_names.sort()
    log_files = map(
        lambda x: os.path.join(target_dir, x),
        file_names)

    summary = {}

    for file in log_files:
        cur_module = file.rsplit('/', 1)[1].split('.')[0]
        sum = {}
        print '\n' + '=' * 80 + '\n' + 'Test results (detailed) for module ' \
            + cur_module + '\n' + '=' * 80
        lines = open(file).readlines()
        for line in lines:
            print line[:-1]
        if lines[-1][:-1] == 'OK':
            sum['errors'] = 0
        elif lines[-1][:6] == 'FAILED':
            if lines[-1][8] == 'f':
                sum['errors'] = int(lines[-1][17:-2])
            else:
                sum['errors'] = int(lines[-1][15:-2])
        else:
            sum['errors'] = 0

        sum['number'] = int(lines[-3].split(' ', 2)[1])

        sum['time'] = float(lines[-3][:-1].rsplit(' ', 1)[1][:-1])

        summary[cur_module] = sum

    print '\n' + '=' * 80 + '\n' + 'Global summary' + '\n' + '=' * 80
    print '\n\tPASSED :\n'
    final = {'number': 0, 'time': 0.00, 'errors': 0}

    for key, value in summary.iteritems():
        if value['errors'] == 0:
            print 'Module %s ran %s tests in %s seconds' % (
                key, value['number'], value['time'])
            for key1, value1 in value.iteritems():
                final[key1] += value1

    print '\n\tFAILED :\n'

    for key, value in summary.iteritems():
        if value['errors'] != 0:
            print 'Module %s ran %s tests in %s seconds with %s failures' % (
                key, value['number'], value['time'], value['errors'])
            for key1, value1 in value.iteritems():
                final[key1] += value1

    print ''
    print 'Total : %s tests in %.2f seconds with %s failures' % (
        final['number'], final['time'], final['errors'])

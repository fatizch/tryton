import os
import subprocess
import sys
import threading
import multiprocessing


def test_module(module, root):
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
            print '=' * 80
            print 'Module : %s, launching test : %s' % (module, filename)
            subprocess.call(
                [sys.executable,
                os.path.join(root, module, 'tests', filename)])
    if nb_test == 0:
        print '=' * 80
        print 'Missing test for module %s' % module


if __name__ == '__main__':
    root = os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..'))
    modules = os.listdir(root)
    num_processes = multiprocessing.cpu_count()
    threads = []

    # run until all the threads are done, and there is no data left
    while threads or modules:
        if (len(threads) < num_processes) and modules:
            t = threading.Thread(
                target=test_module, args=[modules.pop(), root])
            t.setDaemon(True)
            t.start()
            threads.append(t)
        else:
            for thread in threads:
                if not thread.isAlive():
                    threads.remove(thread)

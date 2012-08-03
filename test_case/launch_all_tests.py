import os


if __name__ == '__main__':
    root = os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..'))
    for module in os.listdir(root):
        nb_test = 0
        if not (os.path.isdir(os.path.join(root, module))
            and os.path.isfile(os.path.join(root, module, 'tryton.cfg'))):
            continue
        if os.path.isdir(os.path.join(root, module, 'tests')):
            for filename in os.listdir(os.path.join(root, module, 'tests')):
                if (not filename.startswith('test')
                    or not filename.endswith('.py')):
                    continue
                nb_test += 1
                print '=' * 80
                print 'Module : %s, launching test : %s' % (module, filename)
                execfile(os.path.join(root, module, 'tests', filename))
        if nb_test == 0:
            print '=' * 80
            print 'Missing test for module %s' % module

import sys
import os

WORKSPACE_PATH = 'tryton-workspace'

def is_virtual_env():
    path = sys.prefix
    if hasattr(sys, 'real_prefix'):
        return (True, path)
    return (False, path)

def get_path():
    return is_virtual_env()[1]

def get_workspace_path(path):
    return path + os.sep + WORKSPACE_PATH + os.sep

def set_python_path(root_path):
    sys.path.append(path + 'tryton')
    sys.path.append(path + 'trytond')
    sys.path.append(path + 'proteus')

def set_python_path_if_necessary():
    is_v, path = is_virtual_env()
    if is_v:
        set_python_path(get_workspace_path(path))


if __name__ == '__main__':
    is_v, path = is_virtual_env()
    if is_v:
        print 'Virtual Env detected ! Path => %s' % path
    else:
        print 'Normal env detected'
    set_python_path_if_necessary()
    print 'Python path :'
    print '\n\t'.join([''] + sys.path)
    print ''
    print sys.argv[1:]

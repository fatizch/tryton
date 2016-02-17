def set_module(name):
    global mod
    mod = __import__('broker_%s' % name, globals(), locals(), [], -1)


def get_module():
    global mod
    return mod

import sys

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules import create_graph, get_module_list

from tryton_init import database

modules = sys.argv[1:]
modules_with_deps = set()

with Transaction().start(database, 0, readonly=True):
    modules = Pool().get('ir.module').search(['name', 'in', modules])
    modules_with_deps.update(modules)
    graph, packages, later = create_graph(get_module_list())

    def get_parents(module):
        parents = set(p for p in module.parents)
        for p in module.parents:
            parents.update(get_parents(p))
        return parents

    for module in modules:
        if module.name not in graph:
            missings = []
            for package, deps, xdep, info in packages:
                if package == module.name:
                    missings = [x for x in deps if x not in graph]
            raise Exception('missing_dep %s: %s' % (module.name, missings))
        modules_with_deps.update((m for m in get_parents(module)
                if m.state == 'uninstalled'))
    for module in modules_with_deps:
        print(module.name)

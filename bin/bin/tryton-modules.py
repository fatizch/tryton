# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import sys
import argparse
import psycopg2

from sql import Table, Column


def database_connect():
    conn = psycopg2.connect(
        database=os.environ['PGDATABASE'],
        user=os.environ['PGUSER'],
        password=os.environ['PGPASSWORD'],
        host=os.environ['PGHOST'])
    return conn


def get_module_list(conn, states=None):
    cursor = conn.cursor()
    module_table = Table('ir_module')
    where_clause = None
    if states:
        where_clause = (Column(module_table, 'state').in_(states))

    cursor.execute(*module_table.select(
            Column(module_table, 'name'),
            Column(module_table, 'state'),
            where=where_clause))
    results = cursor.fetchall()
    return results


def depends(modules):
    from trytond.pool import Pool
    from trytond.transaction import Transaction
    from trytond.modules import create_graph, get_module_list

    from tryton_init import database

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


def modules_status(args):
    conn = database_connect()
    modules = args.modules
    for module_name in modules:
        for row in get_module_list(conn):
            if row[0] == module_name:
                print('%s -> %s' % (row[0], row[1]))


def modules_list(args):
    conn = database_connect()
    for row in get_module_list(conn, [
            'activated', 'to_upgrade', 'to_activate']):
        print(row[0])


def main():
    if len(sys.argv) < 2:
        sys.argv.append('--help')

    parser = argparse.ArgumentParser(
        description='Retrieve information on available Coog modules')
    subparser = parser.add_subparsers()
    subparser_list = subparser.add_parser('list',
        help='list available modules')
    subparser_list.set_defaults(func=modules_list)
    subparser_status = subparser.add_parser('status',
        help='get specific module status')
    subparser_status.add_argument('modules', nargs='+')
    subparser_status.set_defaults(func=modules_status)

    args = parser.parse_args(sys.argv[1:])
    args.func(args)
    return


if __name__ == '__main__':
    main()

import sys
import os

from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction

dbname = ''
if len(sys.argv) < 3:
    print "Please provide database name and a list of modules to install"
    sys.exit()
else:
    dbname = sys.argv[1]
    module_names = sys.argv[2:]

config.update_etc(os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..', '..', '..', '..', 'conf', 'trytond.conf')))
CONTEXT = {}


def install_modules(modules):
    '''
        Install the modules if they are not already installed
    '''
    Pool.start()
    pool = Pool(dbname)
    with Transaction().start(dbname, 0, context=CONTEXT):
        pool.init()

    with Transaction().start(dbname, 0, context=CONTEXT) as transaction:
        try:
            Module = pool.get('ir.module')
            Module.install(Module.search([('name', 'in', modules)]))
            langs = [x.code for x in pool.get('ir.lang').search([
                        ('translatable', '=', True)])]
            to_install = [x.name
                for x in Module.search([('state', '=', 'to install')])]
            transaction.cursor.commit()
        except Exception:
            transaction.cursor.rollback()
            raise

    if to_install:
        print 'Installing modules %s' % str(to_install)
        pool.init(update=to_install, lang=langs)
    else:
        print 'Nothing to do'

if __name__ == '__main__':
    install_modules(module_names)

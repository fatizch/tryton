import sys
import os

from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction


dbname = ''
if len(sys.argv) != 2:
    print "Please provide database name as argument"
    sys.exit()
else:
    dbname = sys.argv[1]


config.update_etc(os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..', '..', '..', '..', 'conf', 'trytond.conf')))

CONTEXT = {}


def update_contacts_list():
    Pool.start()
    pool = Pool(dbname)
    with Transaction().start(dbname, 0, context=CONTEXT):
        pool.init()

    with Transaction().start(dbname, 0, context=CONTEXT):
        user_obj = pool.get('res.user')
        user = user_obj.search([('login', '=', 'admin')], limit=1)[0]
        user_id = user.id

    with Transaction().start(dbname, user_id, context=CONTEXT) as transaction:
        pool = Pool()
        Contract = pool.get('contract')
        try:
            contracts = Contract.search(['status', '!=', 'quote'])
            for c in contracts:
                c.update_contacts()
                Contract.save([c])

        except Exception as e:
            transaction.cursor.rollback()
            raise e
        else:
            transaction.cursor.commit()


if __name__ == "__main__":
    update_contacts_list()

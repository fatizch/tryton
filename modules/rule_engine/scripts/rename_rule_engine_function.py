import sys
import os

from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction

dbname = ''
if len(sys.argv) != 3:
    print "Please provide database name and file_name as argument"
    sys.exit()
else:
    dbname = sys.argv[1]
    filename = sys.argv[2]

config.update_etc(os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..', '..', '..', '..', 'conf', 'trytond.conf')))

CONTEXT = {}


def rename_rule_engine_function(to_renames):
    '''
        to_rename is a list of tuple where the first element is the old
        function name and the second is the new function name
    '''
    Pool.start()
    pool = Pool(dbname)
    with Transaction().start(dbname, 0, context=CONTEXT):
        pool.init()

    with Transaction().start(dbname, 0, context=CONTEXT):
        user_obj = pool.get('res.user')
        user = user_obj.search([('login', '=', 'admin')], limit=1)[0]
        user_id = user.id

    with Transaction().start(dbname, user_id, context=CONTEXT) as transaction:
        try:
            RuleEngine = pool.get('rule_engine')
            rules = RuleEngine.search([])
            for rule in rules:
                for old_function, new_function in to_renames:
                    rule.algorithm = rule.algorithm.replace(old_function,
                        new_function)
                rule.save()
        except Exception as e:
            transaction.rollback()
            raise e
        else:
            transaction.commit()

if __name__ == "__main__":
    with open(filename, 'r') as f:
        to_rename = eval(f.read())
    rename_rule_engine_function(to_rename)

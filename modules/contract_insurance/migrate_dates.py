import sys
import os
from dateutil.relativedelta import relativedelta

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
        '..', '..', '..', '..', 'conf', 'trytond.conf')))

CONTEXT = {}


def migrate_dates():
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
            print "migrating options"
            Option = pool.get('contract.option')
            transaction.connection.cursor().execute(
                'select id, start_date from contract_option')
            to_save = []
            values = dict(transaction.connection.cursor().fetchall())
            if values:
                to_save = []
                for option_id, prev_start_date in values.iteritems():
                    option = Option(option_id)
                    start_date = option.parent_contract.start_date
                    if prev_start_date != start_date:
                        option.manual_start_date = prev_start_date
                        to_save.append(option)
                Option.save(to_save)
        except Exception as e:
            transaction.rollback()
            raise e
        else:
            transaction.commit()

    with Transaction().start(dbname, user_id, context=CONTEXT) as transaction:
        print "migrating extra_premiums"
        try:
            ExtraPremium = pool.get('contract.option.extra_premium')
            transaction.connection.cursor().execute(
                'select id, start_date, end_date from '
                'contract_option_extra_premium')
            request_res = {item[0]: (item[1], item[2]) for
                item in transaction.connection.cursor().fetchall()}
            if request_res:
                to_save = []
                for extra_premium_id, dates in request_res.iteritems():
                    extra_premium = ExtraPremium(extra_premium_id)
                    delta = relativedelta(dates[1], dates[0])
                    months = delta.months + 12 * delta.years
                    extra_premium.duration_unit = 'month'
                    if months:
                        extra_premium.duration = months + 1
                    start_date = \
                        extra_premium.option.parent_contract.start_date
                    if dates[0] != start_date:
                        extra_premium.manual_start_date = dates[0]
                    if months and (dates[0] + relativedelta(months=months + 1,
                                days=-1)) != dates[1]:
                        extra_premium.manual_end_date = dates[1]
                        extra_premium.duration = months + 2
                    to_save.append(extra_premium)
                ExtraPremium.save(to_save)
        except Exception as e:
            transaction.rollback()
            raise e
        else:
            transaction.commit()

    with Transaction().start(dbname, user_id, context=CONTEXT) as transaction:
        try:
            transaction.connection.cursor().execute(
                'alter table contract_option ' 'drop column start_date')
        except Exception as e:
            transaction.rollback()
            raise e
        else:
            transaction.commit()
            print "options migration done"

    with Transaction().start(dbname, user_id, context=CONTEXT) as transaction:
        try:
            transaction.connection.cursor().execute('alter table '
                'contract_option_extra_premium drop column end_date')
            transaction.connection.cursor().execute('alter table '
                'contract_option_extra_premium drop column start_date')
        except Exception as e:
            transaction.rollback()
            raise e
        else:
            transaction.commit()
            print "extra_premiums migration done"


if __name__ == "__main__":
    migrate_dates()

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from trytond.pool import Pool
from trytond.transaction import Transaction


def eval_today(fmt=None):
    lang = Transaction().context.get('language')
    Lang = Pool().get('ir.lang')
    lang, = Lang.search([('code', '=', lang)], limit=1)
    if fmt:
        return datetime.datetime.now().strftime(fmt)
    return Lang.strftime(datetime.datetime.now(),
        lang.code, lang.date)

EVAL_METHODS = [
    ('today', eval_today),
    ]

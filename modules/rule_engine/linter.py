# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import pyflakes.messages

from trytond.model import Model
from trytond.rpc import RPC
from rule_engine import check_code


CODE_TEMPLATE = """
from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
Decimal(0)
datetime.date(2000, 1, 1)
relativedelta()

def test():
%s
"""


class Linter(Model):
    "Linter"
    __name__ = 'linter.Linter'

    @classmethod
    def __setup__(cls):
        super(Linter, cls).__setup__()
        cls.__rpc__.update({
                'lint': RPC()
                })

    @classmethod
    def lint(cls, code, known_funcs):
        if not code:
            return []

        errors = []
        code = CODE_TEMPLATE % '\n'.join(' ' + l for l in code.splitlines())
        for message in check_code(code):
            if (isinstance(message, pyflakes.messages.UndefinedName)
                    and message.message_args[0] in known_funcs):
                continue
            # "9" is the number of lines of the template before the actual
            # code
            line_nbr = message.lineno - 9
            errors.append(
                (line_nbr, message.col, message.message % message.message_args)
                )
        return errors

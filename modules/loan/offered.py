# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond import backend
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan_product')

    def get_is_loan_product(self, name):
        for coverage in self.coverages:
            if coverage.is_loan:
                return True
        return False


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan_coverage')
    insured_outstanding_balance = fields.Boolean(
        'Insured Outstanding Amount', help='If set, the insured outstanding '
        'balances wizard will take this coverage for the calculation. '
        'Otherwise it will be ignored')

    @classmethod
    def __register_(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        coverage_h = TableHandler(cls, module_name)
        to_migrate = not coverage_h.column_exist('contract')

        super(OptionDescription, cls).__register__(module_name)

        # Migration from 1.10 : Set Insured Outstanding Amount
        if to_migrate:
            to_update = cls.__table__()
            cursor.execute(*to_update.update(
                    columns=[to_update.insured_outstanding_balance],
                    values=[Literal(True)]))

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('loan', 'Loan'))

    @classmethod
    def default_insured_outstanding_balance(cls):
        return True

    def get_is_loan_coverage(self, name):
        return self.family == 'loan'

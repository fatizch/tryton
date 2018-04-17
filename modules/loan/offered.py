# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Table

from trytond import backend
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__all__ = [
    'ProductConfiguration',
    'Product',
    'OptionDescription',
    ]


class ProductConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'offered.configuration'

    loan_number_sequence = fields.Many2One('ir.sequence',
        'Loan Number Sequence', domain=[('code', '=', 'loan')],
         help='The sequence that will be used to generate numbers for '
        'validated loans')

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')

        # Migration from 1.12 : Set the loan number sequence to use in
        # configuration
        to_migrate = False
        if TableHandler.table_exist('offered_configuration'):
            table = TableHandler(cls, module)
            to_migrate = not table.column_exist('loan_number_sequence')

        super(ProductConfiguration, cls).__register__(module)

        if not to_migrate:
            return

        cursor = Transaction().connection.cursor()
        sequence = Table('ir_sequence')
        cursor.execute(*sequence.select(sequence.id,
                where=sequence.code == 'loan', limit=1))
        matches = cursor.fetchall()
        if not matches:
            return

        table = Table('offered_configuration')
        cursor.execute(*table.update(
                columns=[table.loan_number_sequence],
                values=[Literal(matches[0][0])]))


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

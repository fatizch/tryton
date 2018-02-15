# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table

from trytond.model import ModelSQL
from trytond.transaction import Transaction


class Historizable(ModelSQL):
    '''
        Making a model Historizable will enable client side historization
        activation through the related ir.model instance.

        Historizing will require a manual database update, and un-historizing
        will not remove the history table to avoid accidental data loss. Those
        tables should be checked regularly and manually deleted when it is
        confirmed they should be.
    '''
    @classmethod
    def __setup__(cls):
        force_historize = False
        with Transaction().new_transaction() as t:
            try:
                cursor = t.connection.cursor()
                model_table = Table('ir_model')
                cursor.execute(*model_table.select(model_table.manual_history,
                        where=model_table.model == cls.__name__))
                force_historize = cursor.fetchone()[0] or False
            except Exception:
                t.rollback()
        cls._code_history = getattr(cls, '_code_history', cls._history)
        cls._history = cls._history or force_historize
        super(Historizable, cls).__setup__()

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.operators import UnaryOperator, Operator
from sql.functions import Function as SqlFunction


class TextCat(SqlFunction):
    '''
        Use the textcat function of postgresql to index reference joins:
            Concat('account.invoice,', Cast(invoice.id, 'VARCHAR'))

        Becomes:
            TextCat('account.invoice,', Cast(invoice.id, 'VARCHAR'))

        The associated index would be:
            CREATE INDEX account_invoice_ref_idx ON account_invoice
                USING btree (textcat('account.invoice,', CAST(id AS VARCHAR)))

    '''
    __slots__ = ()
    _function = 'TEXTCAT'


class Interval(UnaryOperator):
    '''
        Allows to define Date intervals.

        Exemple:
            Interval('1 year')
    '''
    __slots__ = ()
    _operator = 'INTERVAL'


class JsonFindKey(Operator):
    '''
        Returns a boolean whose value will be whether the key can be found in
        the json data. The cast from text to json will be performed by default,
        and can be removed by setting the 'convert' attribute to False

                JsonFind(column, key, convert=True)

        Typical case:

                JsonFind(t.extra_data, 'my_key')
    '''
    __slots__ = ('column', 'key', 'convert')
    _operator = '?'

    def __init__(self, column, key, convert=True):
        self.column = column
        self.key = key
        self.convert = convert

    @property
    def _operands(self):
        return (self.column, self.key)

    def __str__(self):
        operator = self._operator
        if self.convert:
            column = '(CAST(%s AS JSONB))' % self._format(self.column)
        else:
            column = '%s' % self._format(self.column)
        return '(%s %s %s)' % (column, operator, self._format(self.key))


class JsonRemoveKey(Operator):
    '''
        Removes the 'key' from the 'column', and returns the result.If the base
        column is a text, it will be automatically converted back and forth.
        This behaviour can be controlled with the 'convert' argument

                JsonRemove(column, key_to_remove, convert=True)
    '''
    __slots__ = ('column', 'key', 'convert')
    _operator = '-'

    def __init__(self, column, key, convert=True):
        self.column = column
        self.key = key
        self.convert = convert

    @property
    def _operands(self):
        return (self.column, self.key)

    def __str__(self):
        operator = self._operator
        if self.convert:
            column = '(CAST(%s AS JSONB))' % self._format(self.column)
        else:
            column = '%s' % self._format(self.column)
        modified = '(%s %s %s)' % (column, operator, self._format(self.key))
        if self.convert:
            modified = '(CAST(%s AS TEXT))' % modified
        return modified


class JsonRenameKey(Operator):
    '''
        Rename a key of a json column to another one.

                JsonRenameKey(column, old_key, new_key, convert=True)
    '''
    __slots__ = ('column', 'old_key', 'new_key', 'convert')

    def __init__(self, column, old_key, new_key, convert=True):
        self.column = column
        self.old_key = old_key
        self.new_key = new_key
        self.convert = convert

    @property
    def _operands(self):
        return (self.column, self.old_key, self.new_key, self.old_key)

    def __str__(self):
        if self.convert:
            column = '(CAST(%s AS JSONB))' % self._format(self.column)
        else:
            column = '%s' % self._format(self.column)

        # {'a': 1, 'b': 2} - 'a' == {'b': 2}
        # {'a': 1, 'b': 2} || {'c': 3} == {'a': 1, 'b': 2, 'c': 3}
        # jsonb_build_object('d', {'a': 1, 'b': 2} -> 'a') == {'d': 1}
        modified = '(%s - %s || jsonb_build_object(%s, %s -> %s))' % (
                column, self._format(self.old_key), self._format(self.new_key),
                column, self._format(self.old_key))
        if self.convert:
            modified = '(CAST(%s AS TEXT))' % modified
        return modified

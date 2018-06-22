# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy

from itertools import chain

from sql import Column, Literal, operators, functions
from sql.conditionals import Coalesce, NullIf
from sql.operators import Concat

from trytond import backend
from trytond.model import fields as tryton_fields
from trytond.pyson import PYSON
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model.fields import SQL_OPERATORS


depends = tryton_fields.depends


class Boolean(tryton_fields.Boolean):
    pass


class Integer(tryton_fields.Integer):
    pass


class Char(tryton_fields.Char):
    pass


class Text(tryton_fields.Text):
    pass


class Float(tryton_fields.Float):
    pass


class Numeric(tryton_fields.Numeric):
    pass


class Date(tryton_fields.Date):
    pass


class DateTime(tryton_fields.DateTime):
    pass


class TimeDelta(tryton_fields.TimeDelta):
    pass


class Timestamp(tryton_fields.Timestamp):
    pass


class Binary(tryton_fields.Binary):
    pass


class Selection(tryton_fields.Selection):
    pass


class Reference(tryton_fields.Reference):
    pass


class Many2One(tryton_fields.Many2One):
    def __init__(self, model_name, string='', left=None, right=None,
            ondelete=None, datetime_field=None, target_search='join',
            search_order=None, search_context=None, help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None, context=None,
            loading='eager'):
        if ondelete is None:
            self._on_delete_not_set = True
            ondelete = 'SET NULL'
        super(Many2One, self).__init__(model_name, string, left, right,
            ondelete, datetime_field, target_search, search_order,
            search_context, help, required, readonly, domain, states,
            select, on_change, on_change_with, depends, context, loading)


class One2Many(tryton_fields.One2Many):
    def __init__(self, *args, **kwargs):
        self._delete_missing = kwargs.pop('delete_missing', False)
        self._target_not_required = kwargs.pop('target_not_required', False)
        self._target_not_indexed = kwargs.pop('target_not_indexed', False)
        super(One2Many, self).__init__(*args, **kwargs)


class One2ManyDomain(One2Many):
    @classmethod
    def init_from_One2Many(cls, source):
        return cls(source.model_name, source.field, source.string,
            source.add_remove, source.order, source.datetime_field,
            source.size, source.help, source.required, source.readonly,
            source.domain, source.states, source.on_change,
            source.on_change_with, source.depends, source.context,
            source.loading, delete_missing=source._delete_missing,
            target_not_required=source._target_not_required,
            target_not_indexed=source._target_not_indexed)

    def get(self, ids, model, name, values=None):
        '''
        Return target records ordered.
        '''
        pool = Pool()
        Relation = pool.get(self.model_name)
        if self.field in Relation._fields:
            field = Relation._fields[self.field]
        else:
            field = Relation._inherit_fields[self.field][2]
        res = {}
        for i in ids:
            res[i] = set(), []

        targets = []
        in_max = Transaction().database.IN_MAX
        for i in range(0, len(ids), in_max):
            sub_ids = ids[i:i + in_max]
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', sub_ids)]

            def clean_domain(the_domain):
                if the_domain[0] in ('OR', 'AND'):
                    final_domain = [the_domain[0]]
                    for elem in the_domain[1:]:
                        good_domain = clean_domain(elem)
                        if not good_domain:
                            final_domain.append(())
                        else:
                            final_domain.append(good_domain)
                elif isinstance(the_domain[0], (tuple, list)):
                    final_domain = []
                    for elem in the_domain:
                        good_domain = clean_domain(elem)
                        if not good_domain:
                            final_domain.append(())
                        else:
                            final_domain.append(good_domain)
                else:
                    has_pyson = False
                    for value in the_domain:
                        if isinstance(value, PYSON):
                            has_pyson = True
                            break
                    if not has_pyson:
                        final_domain = the_domain
                    else:
                        final_domain = None
                return final_domain

            clause.append(clean_domain(self.domain))
            targets.append(Relation.search(clause, order=self.order))
        targets = list(chain(*targets))

        for target in targets:
            origin_id = getattr(target, self.field).id
            if target.id not in res[origin_id][0]:
                # Use set / list combination to manage order
                res[origin_id][0].add(target.id)
                res[origin_id][1].append(target.id)
        return dict((key, tuple(value[1])) for key, value in res.iteritems())


class Many2Many(tryton_fields.Many2Many):
    pass


class Function(tryton_fields.Function):
    def __init__(self, field, getter=None, setter=None, searcher=None,
            loading='lazy', loader=None, updater=None):
        object.__setattr__(self, 'loader', loader)
        object.__setattr__(self, 'updater', updater)
        if loader and not getter:
            getter = loader
        return super(Function, self).__init__(field, getter, setter, searcher,
            loading)

    def __copy__(self):
        return Function(copy.copy(self._field), self.getter,
            setter=self.setter, searcher=self.searcher, loading=self.loading,
            loader=self.loader, updater=self.updater)

    def __deepcopy__(self, memo):
        return Function(copy.deepcopy(self._field, memo), self.getter,
            setter=self.setter, searcher=self.searcher, loading=self.loading,
            loader=self.loader, updater=self.updater)


class MultiValue(tryton_fields.MultiValue):
    pass


class One2One(tryton_fields.One2One):
    pass


class Dict(tryton_fields.Dict):
    def get(self, ids, model, name, values=None):
        result = super(Dict, self).get(ids, model, name, values)
        for k in result:
            if result[k] is None:
                result[k] = {}
        return result


class Unaccent(functions.Function):
    __slots__ = ()
    _function = 'unaccent'


class UnaccentChar(tryton_fields.Char):

    def sql_format(self, value):
        value = super(UnaccentChar, self).sql_format(value)
        if isinstance(value, basestring) and backend.name() == 'postgresql':
            return Unaccent(value)
        return value

    def __get_translation_join(self, Model, name,
            translation, model, table):
        language = Transaction().language
        if Model.__name__ == 'ir.model':
            return table.join(translation, 'LEFT',
                condition=(translation.name == Concat(table.model, name))
                & (translation.res_id == -1)
                & (translation.lang == language)
                & (translation.type == 'model')
                & (translation.fuzzy == Literal(False)))
        elif Model.__name__ == 'ir.model.field':
            if name == 'field_description':
                type_ = 'field'
            else:
                type_ = 'help'
            return table.join(model, 'LEFT',
                condition=model.id == table.model).join(
                    translation, 'LEFT',
                    condition=(translation.name == Concat(Concat(
                                model.model, ','), table.name))
                    & (translation.res_id == -1)
                    & (translation.lang == language)
                    & (translation.type == type_)
                    & (translation.fuzzy == Literal(False)))
        else:
            return table.join(translation, 'LEFT',
                condition=(translation.res_id == table.id)
                & (translation.name == '%s,%s' % (Model.__name__, name))
                & (translation.lang == language)
                & (translation.type == 'model')
                & (translation.fuzzy == Literal(False)))

    def convert_domain(self, domain, tables, Model):
        if self.translate:
            return self.convert_domain_translate(domain, tables, Model)
        table, _ = tables[None]
        name, operator, value = domain
        Operator = tryton_fields.SQL_OPERATORS[operator]
        column = Column(table, name)
        if backend.name() == 'postgresql':
            column = Unaccent(column)
        expression = Operator(column, self._domain_value(operator, value))
        if isinstance(expression, operators.In) and not expression.right:
            expression = Literal(False)
        elif isinstance(expression, operators.NotIn) and not expression.right:
            expression = Literal(True)
        expression = self._domain_add_null(column, operator, value, expression)
        return expression

    def convert_domain_translate(self, domain, tables, Model):
        pool = Pool()
        Translation = pool.get('ir.translation')
        IrModel = pool.get('ir.model')

        table = Model.__table__()
        translation = Translation.__table__()
        model = IrModel.__table__()
        name, operator, value = domain
        join = self.__get_translation_join(Model, name,
            translation, model, table)
        Operator = SQL_OPERATORS[operator]
        column = Coalesce(NullIf(translation.value, ''),
            Column(table, name))
        if backend.name() == 'postgresql':
            column = Unaccent(column)
        where = Operator(column, self._domain_value(operator, value))
        if isinstance(where, operators.In) and not where.right:
            where = Literal(False)
        elif isinstance(where, operators.NotIn) and not where.right:
            where = Literal(True)
        where = self._domain_add_null(column, operator, value, where)
        return tables[None][0].id.in_(join.select(table.id, where=where))


class EmptyNullChar(tryton_fields.Char):
    '''
    Char with '' value is store as Null value in the database
    For example used to add a unicity constraint on field that can be
    presented and store with empty value
    '''

    def sql_format(self, value):
        if value == '':
            return None
        return super(EmptyNullChar, self).sql_format(value)

import logging
import datetime

from sql import Column, Window
from sql.aggregate import Max, Count
from sql.conditionals import Coalesce
from sql.operators import Not

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import fields as tryton_fields


def clear_previous_history(instances, ignore_before=None, include_ignore=True,
        checks=False):
    '''
        Clear history lines for instances. Cleared lines are :

          - All history lines entries after 'ignore_before' but the last one
            for still alive lines

          - All history lines for currently dead lines, after 'ignore_before'

        The call is propagated to O2M fields if they are historized, if they
        are not in the _export_skips method.
        It is possible to further tune the fields on which to propagate through
        declaration of a _clean_history_custom_fields method on a model (see
        fields_to_check).

        If 'ignore_before' is defined, another argument 'include_ignore' is
        accepted to specify whether the given date should be included or not in
        the filter.
    '''
    if not instances:
        return
    if ignore_before is None:
        ignore_before = datetime.date.min
    assert all(x.__class__ == instances[0].__class__
        for x in instances), 'Unauthorized class mixing'
    data_dict = {'model': instances[0].__class__, 'reverse_field': 'id'}
    handle_field([x.id for x in instances], [], data_dict, ignore_before,
        include_ignore, checks=checks)


def fields_to_check(klass):
    pool = Pool()
    to_check = {}
    skips = klass._export_skips()
    for fname, field in klass._fields.iteritems():
        if not isinstance(field, tryton_fields.One2Many):
            continue
        if fname in skips:
            continue
        target = pool.get(field.model_name)
        if not target._history:
            continue
        to_check[fname] = {
            'model': target,
            'reverse_field': field.field,
            }
    custom_method = getattr(klass, '_clean_history_custom_fields', None)
    if custom_method is not None:
        klass._clean_history_custom_fields(to_check)
    return to_check


def handle_field(live_parents, dead_parents, data_dict, ignore_before,
        include_ignore, checks=False):
    if not live_parents and not dead_parents:
        return

    def get_ignore_clause(table):
        if include_ignore:
            return Coalesce(table.write_date,
                table.create_date) > ignore_before
        else:
            return Coalesce(table.write_date,
                table.create_date) >= ignore_before

    cursor = Transaction().connection.cursor()
    target = data_dict['model']
    reverse = data_dict['reverse_field']

    # Find the living
    living = []
    if live_parents:
        target_tbl = target.__table__()
        cursor.execute(*target_tbl.select(target_tbl.id,
                where=Column(target_tbl, reverse).in_(live_parents)))
        living = [x[0] for x in cursor.fetchall()]

    # Look for the dead
    target_hist = target.__table_history__()
    where = Column(target_hist, reverse).in_(live_parents + dead_parents)
    if living:
        where &= Not(target_hist.id.in_(living))
    where &= get_ignore_clause(target_hist)

    cursor.execute(*target_hist.select(target_hist.id,
            where=where, group_by=[target_hist.id]))
    dead = [x[0] for x in cursor.fetchall()]

    # Manage sub fields
    data_dict['sub_fields'] = fields_to_check(target)
    for fname, sub_data in data_dict['sub_fields'].items():
        handle_field(living, dead, sub_data, ignore_before, include_ignore,
            checks=checks)

    if not living and not dead:
        return

    # Filter latest versions
    sub_query = target_hist.select(target_hist.id,
        Column(target_hist, '__id'), Max(Column(target_hist, '__id'),
            window=Window([target_hist.id])).as_('_max_id'),
        where=target_hist.id.in_(living + dead)
        & get_ignore_clause(target_hist))

    # Bury the dead
    where = Column(sub_query, '__id') != sub_query._max_id
    if dead:
        where |= sub_query.id.in_(dead)

    if checks:
        cursor.execute(*sub_query.select(
                Count(Column(sub_query, '__id')),
                where=where))
        to_delete = cursor.fetchone()[0]

        cursor.execute(*target_hist.select(
                Count(Column(target_hist, '__id')),
                where=target_hist.id.in_(living + dead)
                & get_ignore_clause(target_hist)))
        all_histo = cursor.fetchone()[0]
        if all_histo != to_delete + len(living):
            logging.getLogger('model').debug(
                'Bad history deletion : %d != %d + %d (%s)' % (all_histo,
                    to_delete, len(living), target.__name__))
        else:
            logging.getLogger('model').debug(
                'History deletion ok (%s)' % target.__name__)
    else:
        cursor.execute(*target_hist.delete(
                where=Column(target_hist, '__id').in_(
                    sub_query.select(Column(sub_query, '__id'),
                        where=where))))
        logging.getLogger('model').debug(
            'Deleted %d history lines for model %s' % (cursor.rowcount,
                target.__name__))
    data_dict['living'] = living
    data_dict['dead'] = dead

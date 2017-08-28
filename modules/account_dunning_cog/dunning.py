# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict
from operator import attrgetter
from itertools import groupby

from trytond.model import Unique
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields, utils, export, coog_string

__metaclass__ = PoolMeta
__all__ = [
    'Dunning',
    'Level',
    'Procedure',
    ]


class Dunning(export.ExportImportMixin):
    __name__ = 'account.dunning'
    _func_key = 'id'

    last_process_date = fields.Date('Last Process Date', states={
            'invisible': Eval('state') == 'done',
            })
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(Dunning, cls).__setup__()
        cls.line.select = True

    @classmethod
    def dunnings_per_level(cls, dunnings):
        key = attrgetter('level')
        dunnings.sort(key=key)
        return groupby(dunnings, key)

    @classmethod
    def process_dunning_per_level(cls, dunnings):
        dunnings_per_level = cls.dunnings_per_level(dunnings)
        for level, current_dunnings in dunnings_per_level:
            level.process_dunnings(list(current_dunnings))

    @classmethod
    def notify_dunning_per_level(cls, dunnings):
        pool = Pool()
        Event = pool.get('event')
        dunnings_per_level = cls.dunnings_per_level(dunnings)
        for level, current_dunnings in dunnings_per_level:
            if level.event_log_type:
                Event.notify_events(list(current_dunnings),
                    level.event_log_type.code)

    @classmethod
    def _overdue_line_domain(cls, date):
        return super(Dunning, cls)._overdue_line_domain(date) + [
            ('party.dunning_allowed', '=', True)]

    @classmethod
    def process(cls, dunnings):
        cls.process_dunning_per_level(dunnings)
        update_dates = defaultdict(list)
        for dunning in dunnings:
            if dunning.blocked:
                continue
            update_dates[dunning.calculate_last_process_date()].append(
                dunning)
        if update_dates:
            cls.write(*sum([
                        [values, {'state': 'done', 'last_process_date': date}]
                        for date, values in update_dates.iteritems()], []))
        cls.notify_dunning_per_level(dunnings)

    def calculate_last_process_date(self):
        if not self.last_process_date or not self.level.days_from_previous_step:
            return utils.today()
        return self.last_process_date + self.level.overdue

    def get_rec_name(self, name):
        return self.level.rec_name


class Level(export.ExportImportMixin):
    __name__ = 'account.dunning.level'

    name = fields.Char('Name', required=True, translate=True)
    event_log_type = fields.Many2One('event.type', 'Event Log Type',
        ondelete='RESTRICT')
    days_from_previous_step = fields.Boolean('Days Defined From Previous Step',
        help='Days are defined based on the previous level execution date')
    not_mandatory = fields.Boolean('Level Not Mandatory',
        help='If an higher level can be processed, this step will be skipped')
    days = fields.Function(fields.Integer('Days'), 'on_change_with_days',
        'set_days')

    def get_rec_name(self, name):
        return '%s@%s' % (self.name, self.procedure.rec_name)

    def process_dunnings(self, dunnings):
        pass

    def test(self, line, date):
        if self.days_from_previous_step and self.overdue is not None:
            res = False
            if line.dunnings:
                level_rank = self.procedure.levels.index(self)
                previous_level = self.procedure.levels[level_rank - 1]
                if line.dunnings[-1].level == previous_level:
                    res = (date - line.dunnings[-1].last_process_date).days \
                        >= self.overdue.days
        else:
            res = super(Level, self).test(line, date)
        if not res or not self.not_mandatory:
            return res
        # check that next level can be processed if not_mandatory
        level_index = self.procedure.levels.index(self)
        if len(self.procedure.levels) > level_index + 1:
            return not self.procedure.levels[level_index + 1].test(line, date)
        return res

    @fields.depends('overdue')
    def on_change_with_days(self, name=None):
        return self.overdue.days if self.overdue is not None else None

    @classmethod
    def set_days(cls, levels, name, value):
        cls.write(levels, {'overdue': datetime.timedelta(value)
                if value is not None else None})


class Procedure(export.ExportImportMixin):
    __name__ = 'account.dunning.procedure'
    _func_key = 'code'

    code = fields.Char('Code', required=True)

    @classmethod
    def __setup__(cls):
        super(Procedure, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique')]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    @classmethod
    def is_master_object(cls):
        return True

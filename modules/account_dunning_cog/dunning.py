from operator import attrgetter
from itertools import groupby

from trytond.model import Unique
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields, utils, export, coop_string

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
    def process_dunning_per_level(cls, dunnings):
        key = attrgetter('level')
        dunnings.sort(key=key)
        group_dunnings = groupby(dunnings, key)
        for level, current_dunnings in group_dunnings:
            level.process_dunnings(list(current_dunnings))

    @classmethod
    def process(cls, dunnings):
        cls.process_dunning_per_level(dunnings)
        cls.write([d for d in dunnings if not d.blocked], {
                'state': 'done',
                'last_process_date': utils.today(),
                })

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

    def get_rec_name(self, name):
        return '%s@%s' % (self.name, self.procedure.rec_name)

    def process_dunnings(self, dunnings):
        if not self.event_log_type:
            return
        pool = Pool()
        Event = pool.get('event')
        Event.notify_events(dunnings, self.event_log_type.code)

    def test(self, line, date):
        if self.days_from_previous_step and self.days is not None:
            res = False
            if line.dunnings:
                level_rank = self.procedure.levels.index(self)
                previous_level = self.procedure.levels[level_rank - 1]
                if line.dunnings[-1].level == previous_level:
                    res = (date - line.dunnings[-1].last_process_date).days \
                        >= self.days
        else:
            res = super(Level, self).test(line, date)
        if not res or not self.not_mandatory:
            return res
        # check that next level can be processed if not_mandatory
        level_index = self.procedure.levels.index(self)
        if len(self.procedure.levels) > level_index + 1:
            return not self.procedure.levels[level_index + 1].test(line, date)
        return res


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
        return coop_string.slugify(self.name)

    @classmethod
    def is_master_object(cls):
        return True

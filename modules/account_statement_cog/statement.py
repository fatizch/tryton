from trytond.pool import PoolMeta
from trytond.modules.cog_utils import coop_string

__metaclass__ = PoolMeta

__all__ = ['Line']


class Line:
    'Account Statement Line'
    __name__ = 'account.statement.line'

    def get_synthesis_rec_name(self, name):
        return '%s - %s - %s' % (self.statement.journal.rec_name,
            coop_string.date_as_string(self.date),
            self.statement.journal.currency.amount_as_string(self.amount))

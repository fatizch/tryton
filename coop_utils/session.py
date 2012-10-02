import datetime

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView
from trytond.model import fields as fields

from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.modules.coop_utils import utils as utils


class DateClass():
    '''Overriden ir.date class for more accurate date management'''

    __metaclass__ = PoolMeta

    __name__ = 'ir.date'

    @staticmethod
    def today():
        # Session = Pool().get('ir.session')
        # date = Session.business_date
        # return date
        return datetime.date.today()

    @staticmethod
    def system_today():
        return datetime.date.today()


class SessionClass():
    '''Overriden ir.session to add a business date field'''

    __metaclass__ = PoolMeta

    __name__ = 'ir.session'

    business_date = fields.Date(
        'Business Date',
        required=True)

    @staticmethod
    def default_business_date():
        return datetime.date.today()


class AskDate(ModelView):
    '''Asks a new business date for the current session'''
    __name__ = 'utils.change_session.ask_date'

    system_date = fields.Char('System Date', readonly=True)

    current_date = fields.Char('Current Business Date', readonly=True)

    new_date = fields.Date('New Business Date')


class ChangeSessionDate(Wizard):
    '''Wizard allowing to change the current session's business date'''
    __name__ = 'utils.change_session'

    start = 'ask_date'

    ask_date = StateView(
        'utils.change_session.ask_date',
        'coop_utils.ask_new_date',
        [Button('Cancel', 'end', 'tryton-cancel'),
        Button('Apply', 'apply', 'tryton-ok', default=True),
        ])

    apply = StateTransition()

    def default_ask_date(self, wizard, fields):
        date = utils.today()
        return {
            'system_date': '%s' % datetime.date.today(),
            'current_date': '%s' % date,
            'new_date': date}

    def transition_apply(self, wizard):
        Session = Pool().get('ir.session')
        if wizard.ask_date.new_date:
            Session.business_date = wizard.ask_date.new_date
            Session.save()

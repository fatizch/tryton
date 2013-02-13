import copy
import datetime
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.party.contact_mechanism import _TYPES
from trytond.modules.coop_utils import model

MEDIA = _TYPES + [
    ('mail', 'Mail')
]


__all__ = [
    'ContactMechanism',
    'ContactHistory',
]


class ContactMechanism():
    "Contact Mechanism"

    __metaclass__ = PoolMeta

    __name__ = 'party.contact_mechanism'
    _rec_name = 'value'

    @classmethod
    def __setup__(cls):
        super(ContactMechanism, cls).__setup__()
        cls.type = copy.copy(cls.type)
        cls.type.selection.remove(('skype', 'Skype'))
        cls.type.selection.remove(('sip', 'SIP'))
        cls.type.selection.remove(('irc', 'IRC'))
        cls.type.selection.remove(('jabber', 'Jabber'))
        cls._constraints += [('check_email', 'invalid_email')]
        cls._error_messages.update({
            'invalid_email': 'Invalid Email !'})

    def check_email(self):
        if hasattr(self, 'email') and self.email:
            import re
            if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
                return False
        return True

    def pre_validate(self):
        if not self.check_email():
            self.raise_user_error('invalid_email')


class ContactHistory(model.CoopSQL, model.CoopView):
    'Contact History'

    __name__ = 'party.contact_history'

    party = fields.Many2One('party.party', 'Actor',
        ondelete='CASCADE')
    title = fields.Char('Title')
    media = fields.Selection(MEDIA, 'Media')
    contact_mechanism = fields.Many2One('party.contact_mechanism',
        'Contact Mechanism',
        domain=[
            ('party', '=', Eval('party')),
            ('type', '=', Eval('media')),
        ], depends=['party', 'type'],
        states={'invisible': Eval('media') == 'mail'},
        ondelete='RESTRICT')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))],
        depends=['party'],
        states={'invisible': Eval('media') != 'mail'})
    user = fields.Many2One('res.user', 'User')
    #in case the user is deleted, we also keep tracks of his name
    user_name = fields.Char('User Name')
    contact_datetime = fields.DateTime('Date and Time')
    comment = fields.Text('Comment')
    attachment = fields.Many2One('ir.attachment', 'Attachment')

    @staticmethod
    def default_user():
        return Transaction().user

    @staticmethod
    def default_user_name():
        User = Pool().get('res.user')
        return User(Transaction().user).get_rec_name('name')

    @staticmethod
    def default_contact_datetime():
        #TODO: use functional date
        return datetime.datetime.now()

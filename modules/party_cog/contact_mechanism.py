# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql.conditionals import Coalesce

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.party.contact_mechanism import _TYPES
from trytond.modules.coog_core import model, utils, fields, export

MEDIA = _TYPES + [
    ('mail', 'Mail')
    ]

__metaclass__ = PoolMeta
__all__ = [
    'ContactMechanism',
    'PartyInteraction',
    ]


class ContactMechanism(export.ExportImportMixin):
    __name__ = 'party.contact_mechanism'
    _rec_name = 'value'

    @classmethod
    def __setup__(cls):
        super(ContactMechanism, cls).__setup__()
        # TODO : Make it cleaner
        if ('skype', 'Skype') in cls.type.selection:
            cls.type.selection.remove(('skype', 'Skype'))
        if ('sip', 'SIP') in cls.type.selection:
            cls.type.selection.remove(('sip', 'SIP'))
        if ('irc', 'IRC') in cls.type.selection:
            cls.type.selection.remove(('irc', 'IRC'))
        if ('jabber', 'Jabber') in cls.type.selection:
            cls.type.selection.remove(('jabber', 'Jabber'))
        cls._constraints += [('check_email', 'invalid_email')]
        cls._error_messages.update({
                'invalid_email': 'Invalid Email !'})

    def check_email(self):
        if not (hasattr(self, 'type') and self.type == 'email'):
            return True
        if hasattr(self, 'email') and self.email:
            import re
            if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
                return False
        return True

    @fields.depends('email', 'type')
    def pre_validate(self):
        if not self.check_email():
            self.raise_user_error('invalid_email')

    def get_icon(self):
        if self.type == 'phone' or self.type == 'mobile':
            return 'coopengo-phone'
        elif self.type == 'email':
            return 'coopengo-email'

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['value']


class PartyInteraction(model.CoogSQL, model.CoogView):
    'Party Interaction'

    __name__ = 'party.interaction'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        states={'readonly': True})
    title = fields.Char('Title')
    media = fields.Selection(MEDIA, 'Media')
    media_string = media.translated('media')
    contact_mechanism = fields.Many2One('party.contact_mechanism',
        'Contact Mechanism', domain=[
            ('party', '=', Eval('party')),
            ('type', '=', Eval('media')),
            ], depends=['party', 'media'],
        states={'invisible': Eval('media') == 'mail'},
        ondelete='RESTRICT')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))], depends=['party'],
        states={'invisible': Eval('media') != 'mail'}, ondelete='RESTRICT')
    user = fields.Many2One('res.user', 'User', ondelete='RESTRICT')
    contact_datetime = fields.DateTime('Date and Time')
    contact_datetime_str = fields.Function(
        fields.Char('Date and Time'),
        'on_change_with_contact_datetime_str')
    comment = fields.Text('Comment')
    attachment = fields.Many2One('ir.attachment', 'Attachment',
        domain=[('resource', '=', Eval('for_object'))], depends=['for_object'],
        context={'resource': Eval('for_object')}, ondelete='CASCADE')
    for_object = fields.Function(
        fields.Char('For Object', states={'invisible': True}),
        'on_change_with_for_object')
    for_object_ref = fields.Reference('For Object', [('', ''),
            ('party.party', 'Party')],
        states={'readonly': True})

    @staticmethod
    def default_contact_datetime():
        return utils.now()

    @staticmethod
    def default_user():
        return Transaction().user

    @fields.depends('contact_datetime')
    def on_change_with_contact_datetime_str(self, name=None):
        return Pool().get('ir.date').datetime_as_string(self.contact_datetime)

    @fields.depends('party', 'for_object_ref')
    def on_change_with_for_object_ref(self):
        if (hasattr(self, 'for_object_ref') and self.for_object_ref):
            return 'party.party,%s' % self.for_object_ref.id
        if (hasattr(self, 'party') and self.party):
            return 'party.party,%s' % self.party.id

    @fields.depends('for_object_ref')
    def on_change_with_for_object(self, name=None):
        if not (hasattr(self, 'for_object_ref') and self.for_object_ref):
            return ''
        return utils.convert_to_reference(self.for_object_ref)

    @staticmethod
    def order_contact_datetime_str(tables):
        table, _ = tables[None]
        return [Coalesce(table.contact_datetime, datetime.date.min)]

import copy
import datetime
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.party.contact_mechanism import _TYPES
from trytond.modules.cog_utils import model, utils, fields, export

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
        cls.type = copy.copy(cls.type)
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

    def pre_validate(self):
        if not self.check_email():
            self.raise_user_error('invalid_email')

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['type', 'value']

    @classmethod
    def _export_keys(cls):
        return ('party.name', 'type', 'value')


class PartyInteraction(model.CoopSQL, model.CoopView):
    'Party Interaction'

    __name__ = 'party.interaction'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        states={'readonly': True})
    title = fields.Char('Title')
    media = fields.Selection(MEDIA, 'Media')
    contact_mechanism = fields.Many2One('party.contact_mechanism',
        'Contact Mechanism', domain=[
            ('party', '=', Eval('party')),
            ('type', '=', Eval('media')),
            ], depends=['party', 'media'],
        states={'invisible': Eval('media') == 'mail'},
        ondelete='RESTRICT')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))], depends=['party'],
        states={'invisible': Eval('media') != 'mail'})
    user = fields.Many2One('res.user', 'User')
    #in case the user is deleted, we also keep tracks of his name
    user_name = fields.Char('User Name')
    contact_datetime = fields.DateTime('Date and Time')
    comment = fields.Text('Comment')
    attachment = fields.Many2One('ir.attachment', 'Attachment',
        domain=[('resource', '=', Eval('for_object'))], depends=['for_object'],
        context={'resource': Eval('for_object')})
    for_object = fields.Function(
        fields.Char('For Object', states={'invisible': True}),
        'on_change_with_for_object')
    for_object_ref = fields.Reference('For Object', [('party.party', 'Party')],
        states={'readonly': True})

    @staticmethod
    def default_user():
        return Transaction().user

    @classmethod
    def default_party(cls):
        if not 'from_party' in Transaction().context:
            return None

        GoodModel = Pool().get(Transaction().context.get('from_model'))
        good_id = Transaction().context.get('from_party')

        if GoodModel.__name__ == 'party.party':
            return good_id

        good_obj = GoodModel(good_id)
        if not (hasattr(good_obj, 'party') and good_obj.party):
            return None

        return good_obj.party.id

    @classmethod
    def default_for_object_ref(cls):
        return 'party.party,%s' % cls.default_party()

    @classmethod
    def default_for_object(cls):
        return cls.default_for_object_ref()

    @fields.depends('party', 'for_object_ref')
    def on_change_with_for_object_ref(self):
        if (hasattr(self, 'for_object_ref') and self.for_object_ref):
            return self.for_object_ref
        if (hasattr(self, 'party') and self.party):
            return self.party

    @fields.depends('for_object_ref')
    def on_change_with_for_object(self, name=None):
        if not (hasattr(self, 'for_object_ref') and self.for_object_ref):
            return ''
        return utils.convert_to_reference(self.for_object_ref)

    @staticmethod
    def default_user_name():
        User = Pool().get('res.user')
        return User(Transaction().user).get_rec_name('name')

    @staticmethod
    def default_contact_datetime():
        #TODO: use functional date
        return datetime.datetime.now()

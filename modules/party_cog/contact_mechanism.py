# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql.conditionals import Coalesce

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.config import config

from trytond.modules.party.contact_mechanism import _TYPES, _PHONE_TYPES
from trytond.modules.coog_core import model, utils, fields, export

MEDIA = _TYPES + [
    ('mail', 'Mail'),
    ]
VALID_EMAIL_REGEX = r"[^@]+@[^@]+\.[^@]+"

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
        cls.type_string = cls.type.translated('type')
        # The most recent value should appear first
        cls._order.insert(1, ('id', 'DESC'))

        forbidden_types = {'skype', 'sip', 'irc', 'jabber'}
        cls.type.selection = [x for x in cls.type.selection
            if x[0] not in forbidden_types]
        cls._error_messages.update({
                'invalid_email': 'Invalid Email !'})

    @classmethod
    def validate(cls, mechanisms):
        with model.error_manager():
            for mechanism in mechanisms:
                mechanism.check_email()

    @fields.depends('email', 'type')
    def pre_validate(self):
        self.check_email()

    def check_email(self):
        if not (hasattr(self, 'type') and self.type == 'email'):
            return
        if hasattr(self, 'email') and self.email:
            import re
            if not re.match(VALID_EMAIL_REGEX, self.email):
                self.append_functional_error('invalid_email')
        return

    def get_icon(self):
        if self.type == 'phone' or self.type == 'mobile':
            return 'coopengo-phone'
        elif self.type == 'email':
            return 'coopengo-email'

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['value']

    @classmethod
    def add_prefix_to_phone_number(cls, value):
        if value and not value.startswith('+'):
            phone_prefix = config.get('options',
                'phone_prefix', default='+33')
            value = phone_prefix + value[1:]
        return value

    @classmethod
    def create(cls, vlist):
        for data in vlist:
            if data.get('type', None) in _PHONE_TYPES:
                if 'value' not in data:
                    continue
                data['value'] = \
                    cls.add_prefix_to_phone_number(data.get('value', ''))
        return super(ContactMechanism, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        params = iter(args)
        for parties, data in zip(params, params):
            if data.get('type', parties[0].type) in _PHONE_TYPES:
                if 'value' not in data:
                    continue
                data['value'] = \
                    cls.add_prefix_to_phone_number(data.get('value', ''))
        super(ContactMechanism, cls).write(*args)

    @fields.depends('party', 'other_value', 'type', 'value')
    def on_change_other_value(self):
        super(ContactMechanism, self).on_change_other_value()
        self.check_valid_phonenumber()

    @classmethod
    def format_value(cls, value=None, type_=None):
        if phonenumbers and type_ in _PHONE_TYPES:
            value = cls.add_prefix_to_phone_number(value)
        return super(ContactMechanism, cls).format_value(value, type_)

    @classmethod
    def format_value_compact(cls, value=None, type_=None):
        if phonenumbers and type_ in _PHONE_TYPES:
            value = cls.add_prefix_to_phone_number(value)
        super(ContactMechanism, cls).format_value_compact(value, type_)

    def _change_value(self, value, type_):
        if type_ in _PHONE_TYPES:
            value = self.add_prefix_to_phone_number(value)
        super(ContactMechanism, self)._change_value(value, type_)
        self.other_value = self.value

    def get_summary_content(self, label, at_date=None, lang=None):
        return (self.type_string, self.value) if self.value else None


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
        context={'resource': Eval('for_object')}, ondelete='RESTRICT',
        select=True)
    for_object = fields.Function(
        fields.Char('For Object', states={'invisible': True}),
        'on_change_with_for_object')
    for_object_ref = fields.Reference('For Object', 'get_models',
        states={'readonly': True})

    @classmethod
    def get_models(cls):
        return utils.models_get() + [('', '')]

    @staticmethod
    def default_contact_datetime():
        return utils.now()

    @staticmethod
    def default_user():
        return Transaction().user

    @fields.depends('contact_datetime')
    def on_change_with_contact_datetime_str(self, name=None):
        if not self.contact_datetime:
            return ''
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

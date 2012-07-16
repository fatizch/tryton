import copy
from trytond.model import ModelView, ModelSQL

__all__ = ['ContactMechanism']


class ContactMechanism(ModelSQL, ModelView):
    "Contact Mechanism"
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

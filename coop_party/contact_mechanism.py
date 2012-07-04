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
        type = copy.copy(cls.type)
        type.selection.remove(('skype', 'Skype'))
        type.selection.remove(('sip', 'SIP'))
        type.selection.remove(('irc', 'IRC'))
        type.selection.remove(('jabber', 'Jabber'))

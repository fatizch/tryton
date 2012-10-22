import copy
from trytond.pool import PoolMeta

__all__ = ['ContactMechanism']


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

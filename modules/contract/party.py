import copy
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Less

from trytond.modules.coop_utils import fields, utils, coop_string, model

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'ContactHistory',
    ]


class Party():
    'Party'

    __name__ = 'party.party'

    quotes = fields.One2ManyDomain('contract.contract', 'subscriber', 'Quotes',
        domain=[('status', '=', 'quote')])
    last_quote = fields.Function(
        fields.Many2One('contract.contract', 'Last Quote'),
        'get_last_quote_id')
    number_of_quotes = fields.Function(
        fields.Integer('Number of Quotes', on_change_with=['quotes'],
            states={'invisible': True}),
        'on_change_with_number_of_quotes')
    number_of_contracts = fields.Function(
        fields.Integer('Number of Contracts', on_change_with=['contracts'],
            states={'invisible': True}),
        'on_change_with_number_of_contracts')
    main_contract = fields.Function(
        fields.Many2One('contract.contract', 'Main Contract'),
        'get_main_contract_id')
    contracts = fields.One2ManyDomain('contract.contract', 'subscriber',
        'Contracts', domain=[('status', '!=', 'quote')])

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'open_contracts': {
                    'invisible': Less(Eval('number_of_contracts', 0), 1, True),
                    },
                'open_quotes': {
                    'invisible': Less(Eval('number_of_quotes', 0), 1, True),
                    }
                })

    @classmethod
    @model.CoopView.button_action('contract.act_contract_button')
    def open_contracts(cls, objs):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_quote_button')
    def open_quotes(cls, objs):
        pass

    def on_change_with_number_of_contracts(self, name=None):
        return len(self.contracts)

    def on_change_with_number_of_quotes(self, name=None):
        return len(self.quotes)

    def get_main_contract_id(self, name):
        return self.contracts[-1].id if self.contracts else None

    def get_last_quote_id(self, name):
        return self.quotes[-1].id if self.quotes else None

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        if not lang:
            lang = utils.get_user_language()
        res = super(Party, cls).get_summary(parties, name, at_date, lang)
        for party in parties:
            res[party.id] += coop_string.get_field_as_summary(
                party, 'contracts', True, at_date, lang=lang)
        return res


class ContactHistory():
    'Contact History'

    __name__ = 'party.contact_history'

    @classmethod
    def __setup__(cls):
        super(ContactHistory, cls).__setup__()
        cls.for_object_ref = copy.copy(cls.for_object_ref)
        cls.for_object_ref.selection.append(('contract.contract', 'Contract'))

import copy
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Len

from trytond.modules.cog_utils import fields, utils, coop_string, model

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyInteraction',
    ]


class Party:
    __name__ = 'party.party'

    contracts = fields.One2ManyDomain('contract', 'subscriber',
        'Contracts', domain=[('status', '!=', 'quote')])
    quotes = fields.One2ManyDomain('contract', 'subscriber', 'Quotes',
        domain=[('status', '=', 'quote')])

    # Function fields
    last_quote = fields.Function(
        fields.Many2One('contract', 'Last Quote'),
        'on_change_with_last_quote')
    main_contract = fields.Function(
        fields.Many2One('contract', 'Main Contract'),
        'on_change_with_main_contract')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'open_contracts': {
                    'invisible': Len(Eval('contracts', [])) > 0,
                    },
                'open_quotes': {
                    'invisible': Len(Eval('quotes', [])) > 0,                    }
                })

    @classmethod
    def _export_skips(cls):
        result = super(Party, cls)._export_skips()
        result.add('quotes')
        result.add('contracts')
        return result

    @fields.depends('quotes')
    def on_change_with_last_quote(self, name=None):
        return self.quotes[-1].id if self.quotes else None

    @fields.depends('contracts')
    def on_change_with_main_contract(self, name=None):
        return self.contracts[-1].id if self.contracts else None

    @classmethod
    @model.CoopView.button_action('contract.act_contract_button')
    def open_contracts(cls, objs):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_quote_button')
    def open_quotes(cls, objs):
        pass

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        if not lang:
            lang = utils.get_user_language()
        res = super(Party, cls).get_summary(parties, name, at_date, lang)
        for party in parties:
            res[party.id] += coop_string.get_field_as_summary(
                party, 'contracts', True, at_date, lang=lang)
        return res


class PartyInteraction:
    __name__ = 'party.interaction'

    @classmethod
    def __setup__(cls):
        super(PartyInteraction, cls).__setup__()
        cls.for_object_ref = copy.copy(cls.for_object_ref)
        cls.for_object_ref.selection.append(('contract', 'Contract'))

import copy

from sql.aggregate import Max
from sql import Literal

from trytond.wizard import Wizard
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Len, PYSONEncoder

from trytond.modules.cog_utils import fields, utils, coop_string, model
from trytond.modules.cog_utils import UnionMixin

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyInteraction',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    'SynthesisMenuContrat',
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
                    'invisible': Len(Eval('quotes', [])) > 0,
                    }
                })

    @classmethod
    def copy(cls, parties, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('contracts', None)
        default.setdefault('quotes', None)
        return super(Party, cls).copy(parties, default=default)

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
        cls.for_object_ref.selection.append(('contract', 'Contract'))


class SynthesisMenuContrat(model.CoopSQL):
    'Party Synthesis Menu Contract'
    __name__ = 'party.synthesis.menu.contract'

    name = fields.Char('Contracts')
    subscriber = fields.Many2One('party.party', 'Subscriber',
        ondelete='SET NULL')

    @classmethod
    def table_query(cls):
        pool = Pool()
        Contract = pool.get('contract')
        party = pool.get('party.party').__table__()
        contract = Contract.__table__()
        query_table = party.join(contract, 'LEFT OUTER', condition=(
            party.id == contract.subscriber))
        return query_table.select(
            party.id,
            Max(contract.create_uid).as_('create_uid'),
            Max(contract.create_date).as_('create_date'),
            Max(contract.write_uid).as_('write_uid'),
            Max(contract.write_date).as_('write_date'),
            Literal(coop_string.translate_label(cls, 'name')).as_('name'),
            party.id.as_('subscriber'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'contract'

    def get_rec_name(self, name):
        ContractSynthesis = Pool().get('party.synthesis.menu.contract')
        return coop_string.translate_label(ContractSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
            'party.synthesis.menu.contract',
            'contract',
            ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if (Model.__name__ == 'party.synthesis.menu.contract'):
            if name == 'parent':
                return Model._fields['subscriber']
        elif Model.__name__ == 'contract':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['subscriber'])
                union_field.model_name = 'party.synthesis.menu.contract'
                return union_field
            elif name == 'name':
                return Model._fields['contract_number']
        return union_field

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.contract':
            res = 10
        return res


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if (Model.__name__ != 'party.synthesis.menu.contract'):
            return super(SynthesisMenuOpen, self).get_action(record)
        domain = PYSONEncoder().encode([('parties', '=', record.id)])
        actions = {
            'res_model': 'contract',
            'pyson_domain': domain,
            'views': [(None, 'tree'), (None, 'form')]
        }
        return actions

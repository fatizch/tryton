# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy

from sql.aggregate import Max
from sql import Literal

from trytond.rpc import RPC
from trytond.wizard import Wizard
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Len, PYSONEncoder

from trytond.modules.coog_core import fields, coog_string, model

__all__ = [
    'Party',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    'SynthesisMenuContrat',
    'PartyReplace',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    contracts = fields.One2ManyDomain('contract', 'subscriber',
        'Contracts', domain=[('status', '!=', 'quote')])
    related_contracts = fields.Many2Many('contract.contact',
        'party', 'contract', 'Related Contracts')
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
        cls.__rpc__.update({
                'ws_get_covered_contracts_at_date': RPC(
                    readonly=True, instantiate=0)
                })
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
        return super(Party, cls)._export_skips() | {'quotes', 'contracts',
            'related_contracts'}

    @fields.depends('quotes')
    def on_change_with_last_quote(self, name=None):
        return self.quotes[-1].id if self.quotes else None

    @fields.depends('contracts')
    def on_change_with_main_contract(self, name=None):
        return self.contracts[-1].id if self.contracts else None

    @classmethod
    @model.CoogView.button_action('contract.act_contract_button')
    def open_contracts(cls, objs):
        pass

    @classmethod
    @model.CoogView.button_action('contract.act_quote_button')
    def open_quotes(cls, objs):
        pass

    @classmethod
    def get_depending_contracts(cls, parties, date=None):
        return Pool().get('contract').search([
                ('subscriber', 'in', parties),
                ('status', '=', 'active'),
                ])

    def get_summary_content(self, label, at_date=None, lang=None):
        res = super(Party, self).get_summary_content(label, at_date, lang)
        if self.contracts:
            res[1].append(coog_string.get_field_summary(self, 'contracts', True,
                at_date, lang))
        return res

    def ws_get_covered_contracts_at_date(self, date):
        Contract = Pool().get('contract')
        contracts = Contract.get_covered_contracts_from_party(self, date)
        return [c.id for c in contracts]


class SynthesisMenuContrat(model.CoogSQL):
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
            Literal(coog_string.translate_label(cls, 'name')).as_('name'),
            party.id.as_('subscriber'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'contract'

    def get_rec_name(self, name):
        ContractSynthesis = Pool().get('party.synthesis.menu.contract')
        return coog_string.translate_label(ContractSynthesis, 'name')


class SynthesisMenu:
    __metaclass__ = PoolMeta
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


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('contract', 'subscriber'),
            ('contract.contact', 'party'),
            ]

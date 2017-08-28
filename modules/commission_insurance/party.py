# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Not, Eval, Bool, If
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.coog_core import fields, model
from trytond.modules.party_cog.party import STATES_COMPANY


__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker Distribution Network'),
        'get_broker')
    is_broker = fields.Function(
        fields.Boolean('Is Broker',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_broker', searcher='search_is_broker')
    broker_code = fields.Function(
        fields.Char('Broker Code'),
        'get_broker', searcher='search_broker_code')
    agents = fields.One2Many('commission.agent', 'party', 'Agents',
        depends=['is_broker', 'is_insurer'],
        domain=[If(Bool(Eval('is_broker')),
                [('type_', '=', 'agent')], []),
            If(Bool(Eval('is_insurer')),
                [('type_', '=', 'principal')], [])])
    automatic_wire_transfer = fields.Boolean(
        'Use Broker Bank Transfer Journal',
        depends=['is_broker'], states={'invisible': ~Eval('is_broker')})

    def _dunning_allowed(self):
        if self.is_broker:
            return False
        return super(Party, self)._dunning_allowed()

    @classmethod
    def non_customer_clause(cls, clause):
        domain = super(Party, cls).non_customer_clause(clause)
        additional_clause = []
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[2]:
            if clause[1] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [('is_broker', clause[1], False)]
        else:
            if reverse[clause[1]] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [('is_broker', reverse[clause[1]], False)]
        return additional_clause + domain

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'button_commissions_synthesis': {
                    'invisible': ~Eval('is_broker'),
                    },
                'button_party_invoices': {
                    'readonly': (~Eval('is_broker') & ~Eval('is_insurer'))
                    }
                })

    @classmethod
    def __register__(cls, module_name):
        super(Party, cls).__register__(module_name)
        # Migration from 1.3: Drop broker table
        TableHandler = backend.get('TableHandler')
        if TableHandler.table_exist('broker'):
            TableHandler.drop_table('broker', 'broker', True)

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ('/form/notebook/page[@id="role"]/notebook/page[@id="broker"]',
            'states', {'invisible': Bool(~Eval('is_broker'))}),
            (('/form/notebook/page[@id="role"]/group[@id="role_group"]/'
                'group[@id="invisible"]'), 'states', {'invisible': True}),
            ]

    @classmethod
    @model.CoogView.button_action(
        'commission_insurance.act_commission_synthesis_display')
    def button_commissions_synthesis(cls, contracts):
        pass

    @classmethod
    @model.CoogView.button_action(
        'commission_insurance.act_commission_invoice_form')
    def button_party_invoices(cls, parties):
        pass

    @classmethod
    def search_is_broker(cls, name, clause):
        clause = list(clause)
        if clause[2] is True:
            clause[1], clause[2] = ('!=', None)
        elif clause[2] is False:
            clause[2] = None
        return [('network', ) + tuple(clause[1:])]

    @classmethod
    def _export_skips(cls):
        return (super(Party, cls)._export_skips() | set(['agents']))

    @classmethod
    def get_broker(cls, parties, names):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Network = pool.get('distribution.network')
        party = cls.__table__()
        network = Network.__table__()
        values = {}
        values['broker'] = {x.id: None for x in parties}
        values['broker_code'] = {x.id: None for x in parties}
        values['is_broker'] = {x.id: False for x in parties}
        select = party.join(network, 'LEFT OUTER',
            condition=party.id == network.party,
            ).select(party.id, network.id, network.code,
            where=(party.id.in_([x.id for x in parties]))
            )
        cursor.execute(*select)
        for party_id, network_id, code in cursor.fetchall():
            values['broker'][party_id] = network_id
            values['broker_code'][party_id] = code
            values['is_broker'][party_id] = network_id is not None
        return values

    def get_rec_name(self, name):
        if self.is_broker:
            return '[%s] %s' % (self.broker_code, self.name)
        else:
            return super(Party, self).get_rec_name(name)

    def get_icon(self, name=None):
        if self.is_broker:
            return 'coog-broker'
        else:
            return super(Party, self).get_icon(name)

    @classmethod
    def search_broker_code(cls, name, clause):
        return [('network.code',) + tuple(clause[1:])]

    @staticmethod
    def default_automatic_wire_transfer():
        return True

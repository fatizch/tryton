# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Contract',
    'CoveredElement',
    'Beneficiary',
    'ContractBillingInformation',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    allowed_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
            'Allowed Portfolios'),
        'on_change_with_allowed_portfolios')
    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'get_portfolio', searcher='search_portfolio')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.subscriber.depends.append('allowed_portfolios')
        cls.subscriber.domain = [cls.subscriber.domain, ['OR',
                ('portfolio', 'in', Eval('allowed_portfolios')),
                ('portfolio', '=', None)]]

    @fields.depends('dist_network')
    def on_change_with_allowed_portfolios(self, name=None):
        if not self.dist_network:
            return []
        return [x.id for x in self.dist_network.visible_portfolios]

    @fields.depends('subscriber')
    def on_change_with_portfolio(self, name=None):
        return self.subscriber.portfolio.id if self.subscriber and \
            self.subscriber.portfolio else None

    @classmethod
    def get_portfolio(cls, instances, name):
        res = {}
        cursor = Transaction().connection.cursor()
        party = Pool().get('party.party').__table__()
        contract = cls.__table__()

        cursor.execute(*
            contract.join(party, 'LEFT OUTER',
                condition=(contract.subscriber == party.id)).select(
                contract.id, party.portfolio,
                where=(contract.id.in_([x.id for x in instances]))))
        for invoice_id, value in cursor.fetchall():
            res[invoice_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        if clause[1] == '=' and not clause[2]:
            return['OR',
                [('subscriber.portfolio', '=', None)],
                [('subscriber', '=', None)]]
        return [('subscriber.portfolio',) + tuple(clause[1:])]


class CoveredElement:
    __metaclass__ = PoolMeta
    __name__ = 'contract.covered_element'

    allowed_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
        'Allowed Portfolios'),
        'get_allowed_portfolios')

    @classmethod
    def __setup__(cls):
        super(CoveredElement, cls).__setup__()
        cls.party.depends.append('allowed_portfolios')
        cls.party.domain = [cls.party.domain, ['OR',
                ('portfolio', 'in', Eval('allowed_portfolios')),
                ('portfolio', '=', None)]]

    def get_allowed_portfolios(self, name=None):
        if not self.main_contract or not self.main_contract.dist_network:
            return []
        else:
            return [x.id for x in
                self.main_contract.dist_network.visible_portfolios]

    @fields.depends('allowed_portfolios')
    def on_change_contract(self):
        super(CoveredElement, self).on_change_contract()
        self.allowed_portfolios = self.get_allowed_portfolios()

    @fields.depends('allowed_portfolios')
    def on_change_parent(self):
        super(CoveredElement, self).on_change_parent()
        self.allowed_portfolios = self.get_allowed_portfolios()


class Beneficiary:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.beneficiary'

    allowed_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
        'Allowed Portfolios'),
        'get_allowed_portfolios')

    @classmethod
    def __setup__(cls):
        super(Beneficiary, cls).__setup__()
        cls.party.depends.append('allowed_portfolios')
        cls.party.domain = [cls.party.domain, ['OR',
                ('portfolio', 'in', Eval('allowed_portfolios')),
                ('portfolio', '=', None)]]

    @fields.depends('option')
    def get_allowed_portfolios(self, name=None):
        if not self.option.covered_element.contract.dist_network:
            return []
        return [x.id for x in
            self.option.covered_element.contract.dist_network.
            visible_portfolios]

    @fields.depends('allowed_portfolios', 'option')
    def on_change_option(self):
        self.allowed_portfolios = self.get_allowed_portfolios()


class ContractBillingInformation:
    __metaclass__ = PoolMeta
    __name__ = 'contract.billing_information'

    allowed_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
        'Allowed Portfolios'),
        'on_change_with_allowed_portfolios')

    @classmethod
    def __setup__(cls):
        super(ContractBillingInformation, cls).__setup__()
        cls.payer.depends.append('allowed_portfolios')
        cls.payer.domain = [cls.payer.domain, ['OR',
                ('portfolio', 'in', Eval('allowed_portfolios')),
                ('portfolio', '=', None)]]

    @fields.depends('contract')
    def on_change_with_allowed_portfolios(self, name=None):
        return [x.id for x in self.contract.allowed_portfolios]

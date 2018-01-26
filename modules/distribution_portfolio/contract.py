# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
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

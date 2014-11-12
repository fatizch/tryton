from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'ContractSet',
    'Contract',
    ]


class ContractSet(model.CoopSQL, model.CoopView):
    'Contract Set'

    __name__ = 'contract.set'
    _func_key = 'number'
    _rec_name = 'number'

    number = fields.Char('Number', required=True)
    contracts = fields.One2Many('contract', 'contract_set', 'Contracts')
    subscribers = fields.Function(fields.Char('Subscribers'),
        'get_subscribers', searcher='search_subscribers')
    products = fields.Function(fields.Char('Products'),
        'get_products', searcher='search_products')

    @classmethod
    def __setup__(cls):
        super(ContractSet, cls).__setup__()
        cls._sql_constraints = [
            ('number_uniq', 'UNIQUE(number)',
                'The contract set number must be unique.')
        ]

    def get_subscribers(self, name):
        return '\n'.join(contract.subscriber.rec_name
            for contract in self.contracts)

    @classmethod
    def search_subscribers(cls, name, clause):
        return [('contracts.subscriber',) + tuple(clause[1:])]

    def get_products(self, name):
        return '\n'.join(contract.product.rec_name
            for contract in self.contracts)

    @classmethod
    def search_products(cls, name, clause):
        return [('contracts.product',) + tuple(clause[1:])]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['number']


class Contract:
    __name__ = 'contract'
    contract_set = fields.Many2One('contract.set', 'Contract Set',
        ondelete='SET NULL')

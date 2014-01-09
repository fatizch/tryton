from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.cog_utils import fields


__all__ = [
    'ModelCurrency',
    ]


class ModelCurrency(object):
    """
    Define a model with Currency.
    """

    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency',
            on_change=['currency'], states={'invisible': True}),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')

    @classmethod
    def default_currency(cls):
        result = cls.get_currency_from_context()
        if result:
            return result
        # TODO : There is a diffence between test case configuration and global
        # configuration
        config = Pool().get('ir.test_case').get_instance()
        return config.currency.id

    @classmethod
    def get_currency_from_context(cls):
        if 'currency' in Transaction().context:
            return Transaction().context.get('currency')

    def get_currency(self):
        raise NotImplementedError

    def on_change_currency(self):
        digits = self.currency.digits if self.currency else 2
        symbol = self.currency.symbol if self.currency else ''
        return {'currency_digits': digits, 'currency_symbol': symbol}

    def get_currency_id(self, name):
        return self.get_currency().id

    def get_currency_digits(self, name):
        return self.on_change_currency()['currency_digits']

    def get_currency_symbol(self, name):
        return self.on_change_currency()['currency_symbol']

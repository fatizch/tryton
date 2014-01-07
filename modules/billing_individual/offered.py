from trytond.pyson import Eval
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import model, fields

from payment_rule import PAYMENT_DELAYS


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'ProductPaymentMethodRelation',
    'OptionDescription',
    ]


class Product:
    __name__ = 'offered.product'

    payment_delay = fields.Selection(PAYMENT_DELAYS, 'Payment delay')
    payment_methods = fields.One2Many(
        'offered.product-billing.payment.method', 'product',
        'Payment Methods', order=[('order', 'ASC')],
        domain=[('payment_method.payment_rule.payment_mode', '=',
                Eval('payment_delay', ''))],
        depends=['payment_delay'])
    account_for_billing = fields.Many2One('account.account',
        'Account for billing', required=True, depends=['company'],
        domain=[('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        ondelete='RESTRICT')

    def get_default_payment_method(self):
        if not self.payment_methods:
            return None
        return self.payment_methods[0].payment_method

    def get_allowed_payment_methods(self):
        result = []
        for elem in self.payment_methods:
            result.append(elem.payment_method)
        return result

    def get_account_for_billing(self):
        return self.account_for_billing

    @classmethod
    def default_payment_delay(cls):
        return 'in_advance'

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Product, cls).get_var_names_for_full_extract()
        res.extend(['payment_methods'])
        return res


class ProductPaymentMethodRelation(model.CoopSQL, model.CoopView):
    'Product Payment Method Relation'

    __name__ = 'offered.product-billing.payment.method'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    payment_method = fields.Many2One('billing.payment.method',
        'Payment Method', ondelete='RESTRICT')
    order = fields.Integer('Order', required=True)

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['order', 'payment_method']


class OptionDescription:
    __name__ = 'offered.option.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        states={
            'required': ~Eval('is_package'),
            'invisible': ~~Eval('is_package'),
            }, ondelete='RESTRICT')

    def get_account_for_billing(self):
        return self.account_for_billing

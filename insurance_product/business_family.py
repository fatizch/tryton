from trytond.model import fields as fields

from trytond.pool import Pool

from trytond.modules.coop_utils import model as model
from trytond.modules.coop_utils import utils as utils


__all__ = ['BusinessFamily']


class BusinessFamily(model.CoopSQL, model.CoopView):
    'Business Family'

    __name__ = 'ins_product_utils.business_family'

    name = fields.Char('Name')

    code = fields.Char('Code')

    contract_extension = fields.Selection(
        'get_allowed_extensions',
        'Contract Extension')

    is_default = fields.Boolean('Is Default')

    @classmethod
    def __setup__(cls):
        super(BusinessFamily, cls).__setup__()
        cls._constraints += [('check_default', 'only_one_default')]
        cls._error_messages.update({'only_one_default':
            'There can be only one default business family !'})

    @staticmethod
    def get_allowed_extensions():
        models = utils.get_descendents('ins_contract.generic_extension', True)
        models.remove('ins_contract.generic_extension')
        return map(lambda x: (x, x.__doc__), models)

    @staticmethod
    def default_is_default():
        already_exists = Pool().get(
            'ins_product_utils.business_family').search([])
        if not already_exists:
            return True
        return False

    def check_default(self):
        if hasattr(self, 'is_default') and self.is_default:
            default = self.search([('is_default', '=', True)])
            if default and len(default) > 1:
                return False
        return True

    def get_extension_model(self, contract):
        target_model = self.contract_extension
        for field_name, field in contract._fields.iteritems():
            if hasattr(field,
                    'model_name') and field.model_name == target_model:
                return field_name

from trytond.pyson import Eval
from trytond.pool import Pool

from trytond.modules.coop_utils import fields
from trytond.modules.coop_process import ProcessFinder, ProcessParameters


__all__ = [
    'EndorsementProcessParameters',
    'EndorsementProcessFinder',
    ]


class EndorsementProcessParameters(ProcessParameters):
    'Endorsement Process Parameters'

    __name__ = 'contract.endorsement_process_parameters'

    contract = fields.Many2One('contract', 'Contract',
        on_change=['contract', 'product'],
        domain=[
            ('status', '=', 'active'),
            ('product_kind', '=', 'insurance'),
        ])
    product = fields.Many2One('offered.product', 'Product',
        states={'invisible': True})

    @classmethod
    def build_process_domain(cls):
        result = super(
            EndorsementProcessParameters, cls).build_process_domain()
        result.append(('for_products', '=', Eval('product')))
        result.append(('kind', '=', 'endorsement'))
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            EndorsementProcessParameters, cls).build_process_depends()
        result.append('product')
        return result

    def on_change_contract(self):
        res = {}
        res['product'] = self.contract.offered.id if self.contract else None
        return res

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'contract')])[0].id


class EndorsementProcessFinder(ProcessFinder):
    'Endorsement Process Finder'

    __name__ = 'contract.endorsement_process_finder'

    @classmethod
    def get_parameters_model(cls):
        return 'contract.endorsement_process_parameters'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'insurance_contract_subscription',
            'endorsement_process_parameters_form')

    def search_main_object(self):
        return self.process_parameters.contract

    def update_main_object(self, main_obj):
        main_obj.temp_endorsment_date = self.process_parameters.date
        super(EndorsementProcessFinder, self).update_main_object(main_obj)

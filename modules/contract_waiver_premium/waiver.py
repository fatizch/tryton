from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'PremiumWaiverContractOption',
    'PremiumWaiver',
    ]


class PremiumWaiverContractOption(model.CoopSQL, model.CoopView):
    'Premium Waiver - Contract Option Relation'

    __name__ = 'contract.waiver_premium-contract.option'

    option = fields.Many2One('contract.option', 'Option', required=True,
        ondelete='CASCADE', select=True)
    waiver = fields.Many2One('contract.waiver_premium', 'Waiver',
        required=True, ondelete='CASCADE', select=True)


class PremiumWaiver(model.CoopSQL, model.CoopView):
    'Premium Waiver'

    __name__ = 'contract.waiver_premium'

    start_date = fields.Date('Start Date', required=True, readonly=True)
    end_date = fields.Date('End Date', readonly=True)
    options = fields.Many2Many('contract.waiver_premium-contract.option',
        'waiver', 'option', 'Options', readonly=True)
    options_names = fields.Function(
        fields.Char('Options Names'),
        'get_options_names')
    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True)

    @classmethod
    def __setup__(cls):
        super(PremiumWaiver, cls).__setup__()
        cls.contract.readonly = True

    def get_options_names(self, name):
        return ', '.join([x.rec_name for x in self.options])

    @staticmethod
    def get_waiver_line_fields():
        return ['type', 'description', 'origin', 'quantity',
            'unit', 'unit_price', 'invoice_type', 'coverage_start',
            'coverage_end', 'coverage']

    @staticmethod
    def get_waiver_line_detail_fields():
        return ['rated_entity', 'frequency', 'rate',
            'premium', 'loan', 'coverage']

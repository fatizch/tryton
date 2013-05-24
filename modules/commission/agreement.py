import copy

from trytond.pyson import Eval

from trytond.modules.coop_utils import fields, model, utils
from trytond.modules.contract import contract


__all__ = [
    'CommissionAgreement',
    'CommissionOption',
    'CompensatedOption',
    ]


class CommissionAgreement(contract.Contract):
    'Commission Agreement'

    __name__ = 'commission.agreement'
    _table = None

    @classmethod
    def get_options_model_name(cls):
        return 'commission.option'

    @classmethod
    def get_offered_name(cls):
        return 'commission.commission_plan', 'Commission Plan'

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'subscriber', [('is_broker', '=', True)])
        cls.subscriber = copy.copy(cls.subscriber)
        cls.subscriber.string = 'Broker'
        cls.contract_number = copy.copy(cls.contract_number)
        cls.contract_number.string = 'Reference'
        super(CommissionAgreement, cls).__setup__()


class CommissionOption(contract.SubscribedCoverage):
    'Commission Option'

    __name__ = 'commission.option'
    _table = None

    compensated_options = fields.One2Many('commission.compensated_option',
        'com_option', 'Compensated Options')

    @classmethod
    def get_contract_model_name(cls):
        return 'commission.agreement'

    @classmethod
    def get_offered_name(cls):
        return 'commission.commission_component', 'Coverage'


class CompensatedOption(model.CoopSQL, model.CoopView):
    'Compensated Option'

    __name__ = 'commission.compensated_option'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    com_option = fields.Many2One('commission.option', 'Commission Option',
        ondelete='RESTRICT')
    subs_option = fields.Many2One('ins_contract.option',
        'Subscribed Coverage', ondelete='CASCADE')
    use_specific_rate = fields.Boolean('Specific Rate')
    rate = fields.Numeric('Rate', states={
            'invisible': ~Eval('use_specific_rate'),
            'required': ~~Eval('use_specific_rate'),
            })

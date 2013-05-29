import copy

from trytond.pyson import Eval, Equal, If
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields, model, utils


__all__ = [
    'CommissionAgreement',
    'CommissionOption',
    'CompensatedOption',
    ]


class CommissionAgreement():
    'Commission Agreement'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    plan = fields.Many2One('commission.commission_plan', 'Plan')

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'subscriber', [If(
                    Equal(Eval('kind'), 'commission'),
                    ('is_broker', '=', True),
                    (),
                    )])
        utils.update_depends(cls, 'subscriber', ['kind'])
        cls.subscriber = copy.copy(cls.subscriber)
        cls.subscriber.string = 'Broker'
        cls.contract_number = copy.copy(cls.contract_number)
        cls.contract_number.string = 'Reference'
        super(CommissionAgreement, cls).__setup__()

    @classmethod
    def get_possible_contract_kind(cls):
        res = super(CommissionAgreement, cls).get_possible_contract_kind()
        res.extend([
                ('commission', 'Commission'),
                ])
        return list(set(res))


class CommissionOption():
    'Commission Option'

    __name__ = 'contract.subscribed_option'
    __metaclass__ = PoolMeta

    com_option = fields.Many2One('commission.compensated_option', 'Com Option')
    compensated_options = fields.One2Many('commission.compensated_option',
        'com_option', 'Compensated Options')


class CompensatedOption(model.CoopSQL, model.CoopView):
    'Compensated Option'

    __name__ = 'commission.compensated_option'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    com_option = fields.Many2One('contract.subscribed_option',
        'Commission Option', ondelete='RESTRICT')
    subs_option = fields.Many2One('contract.subscribed_option',
        'Subscribed Coverage', ondelete='CASCADE')
    use_specific_rate = fields.Boolean('Specific Rate')
    rate = fields.Numeric('Rate', states={
            'invisible': ~Eval('use_specific_rate'),
            'required': ~~Eval('use_specific_rate'),
            })

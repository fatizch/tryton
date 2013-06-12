from trytond.pyson import Eval, Equal, If
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

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

    @classmethod
    def __setup__(cls):
        super(CommissionAgreement, cls).__setup__()
        utils.update_domain(cls, 'subscriber', [If(
                    Equal(Eval('product_kind'), 'commission'),
                    ('is_broker', '=', True),
                    (),
                    )])
        utils.update_depends(cls, 'subscriber', ['product_kind'])

    def update_management_roles(self):
        super(CommissionAgreement, self).update_management_roles()
        role = self.get_management_role('commission')
        agreement = role.protocol if role else None
        if not agreement:
            return
        for option in self.options:
            option.update_commissions(agreement)


class CommissionOption():
    'Commission Option'

    __name__ = 'contract.subscribed_option'
    __metaclass__ = PoolMeta

    compensated_options = fields.One2Many('commission.compensated_option',
        'com_option', 'Compensated Options',
        states={'invisible': Eval('coverage_kind') != 'commission'},
        context={'from': 'com'})
    commissions = fields.One2Many('commission.compensated_option',
        'subs_option', 'Commissions',
        states={'invisible': Eval('coverage_kind') != 'insurance'},
        context={'from': 'subscribed'})

    def update_commissions(self, agreement):
        CompOption = Pool().get('commission.compensated_option')
        for com_option in agreement.options:
            if not self.offered in com_option.offered.coverages:
                continue
            good_comp_option = None
            for comp_option in self.commissions:
                if comp_option.com_option == com_option:
                    good_comp_option = comp_option
                    break
            if not good_comp_option:
                good_comp_option = CompOption()
                good_comp_option.com_option = com_option
                if not self.commissions:
                    self.commissions = []
                self.commissions = list(self.commissions)
                self.commissions.append(good_comp_option)
            good_comp_option.start_date = self.start_date
            self.save()


class CompensatedOption(model.CoopSQL, model.CoopView):
    'Compensated Option'

    __name__ = 'commission.compensated_option'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    com_option = fields.Many2One('contract.subscribed_option',
        'Commission Option', domain=[('coverage_kind', '=', 'commission')],
        ondelete='RESTRICT')
    subs_option = fields.Many2One('contract.subscribed_option',
        'Subscribed Coverage', domain=[('coverage_kind', '=', 'insurance')],
        ondelete='CASCADE')
    use_specific_rate = fields.Boolean('Specific Rate')
    rate = fields.Numeric('Rate', states={
            'invisible': ~Eval('use_specific_rate'),
            'required': ~~Eval('use_specific_rate'),
            })

    def get_rec_name(self, name):
        option = None
        if Transaction().context.get('from') == 'com':
            option = self.subs_option
        else:
            option = self.com_option
        if not option:
            return ''
        return '%s - %s (%s)' % (
            option.current_policy_owner.rec_name,
            option.contract.contract_number
            if option.contract.contract_number else '',
            option.rec_name,
            )

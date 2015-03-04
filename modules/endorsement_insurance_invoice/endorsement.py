import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import relation_mixin

__metaclass__ = PoolMeta
__all__ = [
    'BillingInformation',
    'Contract',
    'Endorsement',
    'EndorsementContract',
    'EndorsementBillingInformation',
    ]


class BillingInformation(object):
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.billing_information'


class Contract:
    __name__ = 'contract'

    def _get_invoice_rrule_and_billing_information(self, start):
        invoice_rrule = super(Contract,
            self)._get_invoice_rrule_and_billing_information(start)
        Endorsement = Pool().get('endorsement')
        endorsement_dates = [datetime.datetime.combine(
                endorsement.effective_date, datetime.time()) or
            endorsement.application_date
            for endorsement in Endorsement.search([
                        ('contracts', '=', self.id),
                        ('state', '=', 'applied')])
            if endorsement.definition.requires_contract_rebill]
        if endorsement_dates:
            invoice_rrule[0].rrule(endorsement_dates)
        return invoice_rrule

    @classmethod
    def rebill_after_endorsement(cls, contracts, caller=None):
        if Transaction().context.get('endorsement_soft_apply', False):
            return
        if not isinstance(caller, (tuple, list)):
            caller = [caller]
        if caller[0].__name__ != 'endorsement.contract':
            return
        rebill_dict = {}
        for endorsement in caller:
            if endorsement.contract not in contracts:
                continue
            if (endorsement.endorsement.effective_date ==
                    endorsement.contract.start_date):
                # The endorsement (maybe) changed the start_date, we should
                # recalculate everything
                base_date = datetime.date.min
            else:
                base_date = endorsement.endorsement.effective_date
            rebill_dict[endorsement.contract] = min(
                rebill_dict.get(endorsement.contract,
                    endorsement.endorsement.effective_date),
                base_date)
        for contract, date in rebill_dict.iteritems():
            contract.rebill(date)


class Endorsement:
    __name__ = 'endorsement'

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind == 'billing_information':
            return Pool().get('endorsement.contract')(endorsement=self)
        return super(Endorsement, self).new_endorsement(endorsement_part)

    @classmethod
    def _draft(cls, endorsements):
        super(Endorsement, cls)._draft(endorsements)
        # For now there are no "post_draft_actions" on endorsement parts
        to_rebill = [x for x in endorsements
            if x.definition.requires_contract_rebill]
        if to_rebill:
            Pool().get('contract').rebill_after_endorsement(sum(
                    [list(x.contracts) for x in to_rebill], []),
                caller=sum([list(x.contract_endorsements)
                        for x in to_rebill], []))

    def find_parts(self, endorsement_part):
        if endorsement_part.kind in 'billing_information':
            return self.contract_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)


class EndorsementContract:
    __name__ = 'endorsement.contract'

    billing_informations = fields.One2Many(
        'endorsement.contract.billing_information',
        'contract_endorsement', 'Billing Informations', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'],
        context={'definition': Eval('definition')})

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._error_messages.update({
                'mes_billing_modifications': 'Billing Modifications',
                })

    def get_endorsement_summary(self, name):
        result = super(EndorsementContract, self).get_endorsement_summary(name)
        previous_billing_information = self.base_instance.billing_information
        billing_summary = '\n'.join([billing_information.get_summary(
                    'contract.billing_information',
                    previous_billing_information, indent=4)
                for billing_information in self.billing_informations])
        if billing_summary:
            result += '  %s :\n' % self.raise_user_error(
                'mes_billing_modifications', raise_exception=False)
            result += billing_summary
            result += '\n\n'
        return result

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        contract_idx = order.index('contract')
        order.insert(contract_idx + 1, 'contract.billing_information')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.billing_information'] += \
                contract.billing_informations

    def apply_values(self):
        values = super(EndorsementContract, self).apply_values()
        billing_informations = []
        for billing_information in self.billing_informations:
            billing_informations.append(billing_information.apply_values())
        if billing_informations:
            values['billing_informations'] = billing_informations
        return values

    def set_applied_on(self, datetime):
        super(EndorsementContract, self).set_applied_on(datetime)
        for billing_information in self.billing_informations:
            billing_information.applied_on = datetime
        self.billing_informations = list(self.billing_informations)


class EndorsementBillingInformation(relation_mixin(
            'endorsement.contract.billing_information.field',
            'billing_information', 'contract.billing_information',
            'Billing Informations'),
        model.CoopSQL, model.CoopView):
    'Endorsement Billing Information'

    __name__ = 'endorsement.contract.billing_information'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementBillingInformation, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button
from trytond.pyson import Eval, If

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import EndorsementWizardStepMixin

__metaclass__ = PoolMeta
__all__ = [
    'ChangeContractBroker',
    'ChangeContractCommission',
    'StartEndorsement',
    ]


class ChangeContractBroker(EndorsementWizardStepMixin):
    'Change Contract Broker'

    __name__ = 'endorsement.contract.change_broker'

    agent = fields.Many2One('commission.agent', 'New Agent',
        domain=[
            ('type_', '=', 'agent'),
            ('plan.commissioned_products', '=', Eval('product')),
            If(~Eval('broker_party'),
                (),
                ('party', '=', Eval('broker_party')),
                )
            ],
        depends=['broker_party', 'product'])
    broker = fields.Many2One('distribution.network', 'New Broker',
        domain=[('party.agents', '!=', None)])
    broker_party = fields.Many2One('party.party', 'New Broker Party',
        states={'invisible': True})
    current_broker = fields.Many2One('distribution.network', 'Current Broker',
        readonly=True)
    current_agent = fields.Many2One('commission.agent', 'Current Agent',
        readonly=True)
    product = fields.Many2One('offered.product', 'Product', readonly=True,
        states={'invisible': True})

    @classmethod
    def is_multi_instance(cls):
        return False

    @fields.depends('broker')
    def on_change_with_broker_party(self):
        return self.broker.party.id if self.broker else None

    @classmethod
    def _contract_fields_to_extract(cls):
        return {
            'contract': ['agent', 'broker', 'broker_party', 'product'],
            }

    @classmethod
    def update_default_values(cls, wizard, endorsement, default_values):
        updated_values = getattr(endorsement, 'values', {})
        new_defaults = {}
        for fname in cls._contract_fields_to_extract()['contract']:
            new_defaults[fname] = updated_values.get(fname, getattr(
                    endorsement.contract, fname).id)
            new_defaults['current_%s' % fname] = getattr(
                endorsement.contract, fname).id
        return new_defaults

    def update_endorsement(self, base_endorsement, wizard):
        base_endorsement.values = getattr(base_endorsement, 'values', {})
        for fname in self._contract_fields_to_extract()['contract']:
            fvalue = getattr(self, fname)
            if fvalue == getattr(base_endorsement.contract, fname):
                base_endorsement.values.pop(fname, None)
            else:
                base_endorsement.values[fname] = fvalue.id if fvalue else None
        base_endorsement.save()


class ChangeContractCommission(ChangeContractBroker):
    'Change Contract Commission'

    __name__ = 'endorsement.contract.change_commission'

    current_plan = fields.Many2One('commission.plan', 'Current Plan',
        readonly=True, states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(ChangeContractCommission, cls).__setup__()
        cls.agent.domain = cls.agent.domain + [
            ('plan', '=', Eval('current_plan'))]
        cls.agent.depends.append('current_plan')

    @classmethod
    def update_default_values(cls, wizard, endorsement, default_values):
        new_defaults = super(ChangeContractCommission,
            cls).update_default_values(wizard, endorsement, default_values)
        if not endorsement.contract.agent:
            return new_defaults
        new_defaults['current_plan'] = endorsement.contract.agent.plan.id
        return new_defaults


class StartEndorsement:
    __name__ = 'endorsement.start'

    change_commission = StateView('endorsement.contract.change_commission',
        'endorsement_commission.change_contract_commission_view_form', [
            Button('Previous', 'change_commission_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'change_commission_next', 'tryton-go-next',
                default=True)])
    change_commission_previous = StateTransition()
    change_commission_next = StateTransition()
    change_broker = StateView('endorsement.contract.change_broker',
        'endorsement_commission.change_contract_broker_view_form', [
            Button('Previous', 'change_broker_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'change_broker_next', 'tryton-go-next',
                default=True)])
    change_broker_previous = StateTransition()
    change_broker_next = StateTransition()

    def default_change_commission(self, name):
        ContractEndorsement = Pool().get('endorsement.contract')
        endorsement_part = self.get_endorsement_part_for_state(
            'change_commission')
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            }
        endorsements = self.get_endorsements_for_state('change_commission')
        if not endorsements:
            if self.select_endorsement.contract:
                endorsements = [ContractEndorsement(definition=self.definition,
                        endorsement=self.endorsement,
                        contract=self.select_endorsement.contract)]
            else:
                return result
        ChangeContractCommission = Pool().get(
            'endorsement.contract.change_commission')
        result.update(ChangeContractCommission.update_default_values(self,
                endorsements[0], result))
        return result

    def transition_change_commission_previous(self):
        self.end_current_part('change_commission')
        return self.get_state_before('change_commission')

    def transition_change_commission_next(self):
        self.end_current_part('change_commission')
        return self.get_next_state('change_commission')

    def default_change_broker(self, name):
        ContractEndorsement = Pool().get('endorsement.contract')
        endorsement_part = self.get_endorsement_part_for_state(
            'change_broker')
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            }
        endorsements = self.get_endorsements_for_state('change_broker')
        if not endorsements:
            if self.select_endorsement.contract:
                endorsements = [ContractEndorsement(definition=self.definition,
                        endorsement=self.endorsement,
                        contract=self.select_endorsement.contract)]
            else:
                return result
        ChangeContractBroker = Pool().get('endorsement.contract.change_broker')
        result.update(ChangeContractBroker.update_default_values(self,
                endorsements[0], result))
        return result

    def transition_change_broker_previous(self):
        self.end_current_part('change_broker')
        return self.get_state_before('change_broker')

    def transition_change_broker_next(self):
        self.end_current_part('change_broker')
        return self.get_next_state('change_broker')

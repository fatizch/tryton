from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import EndorsementWizardStepMixin


__metaclass__ = PoolMeta
__all__ = [
    'OptionBeneficiaryDisplayer',
    'ManageBeneficiaries',
    'StartEndorsement',
    ]


class OptionBeneficiaryDisplayer(model.CoopView):
    'Option Beneficiary Displayer'

    __name__ = 'endorsement.contract.beneficiary.manage.option'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', readonly=True)
    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Covered Element',
        readonly=True)
    covered_element_name = fields.Char('Covered Element', readonly=True)
    option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option', 'Option Endorsement',
        readonly=True)
    option_name = fields.Char('Option', readonly=True)
    current_option = fields.One2Many('contract.option', None,
        'Current Version', readonly=True)
    new_option = fields.One2Many('contract.option', None, 'New Version')


class ManageBeneficiaries(model.CoopView, EndorsementWizardStepMixin):
    'Manage Beneficiaries'

    __name__ = 'endorsement.contract.beneficiary.manage'

    options = fields.One2Many('endorsement.contract.beneficiary.manage.option',
        None, 'Options with Beneficiaries')

    @staticmethod
    def update_dict(to_update, key, value):
        # TODO : find a cleaner endorsement class detection
        to_update[key] = to_update[key + '_endorsement'] = None
        if hasattr(value, 'get_endorsed_record'):
            to_update[key + '_endorsement'] = value.id
            to_update[key] = value.relation
        else:
            to_update[key] = value.id
        to_update[key + '_name'] = value.rec_name

    @classmethod
    def _option_fields_to_extract(cls):
        return {
            'contract.option': ['coverage', 'has_beneficiary_clause',
                'beneficiary_clause', 'beneficiaries',
                'customized_beneficiary_clause', 'contract_status'],
            'contract.option.beneficiary': ['accepting', 'party', 'address',
                'reference', 'share'],
            }

    @classmethod
    def create_displayer(cls, option, template):
        pool = Pool()
        Option = pool.get('contract.option')
        Beneficiary = pool.get('contract.option.beneficiary')
        displayer = template.copy()
        if option.__name__ == 'endorsement.contract.covered_element.option':
            displayer['option_endorsement'] = option.id
            if option.action == 'add':
                instance = Option(**option.values)
                displayer['current_option'] = []
            elif option.action == 'update':
                instance = option.option
                displayer['current_option'] = [instance.id]
                for fname, fvalue in option.values.iteritems():
                    setattr(instance, fname, fvalue)
            elif option.action == 'remove':
                return
            if option.beneficiaries:
                old_beneficiaries = list(instance.beneficiaries)
                instance.beneficiaries = []
                for beneficiary in option.beneficiaries:
                    if beneficiary.action == 'add':
                        instance.beneficiaries.append(
                            Beneficiary(**beneficiary.values))
                    elif beneficiary.action == 'remove':
                        old_beneficiaries.remove(beneficiary.beneficiary)
                    else:
                        old_beneficiaries.remove(beneficiary.beneficiary)
                        instance.beneficiaries.append(
                            beneficiary.beneficiary)
                        for k, v in beneficiary.values.iteritems():
                            setattr(beneficiary.beneficiary, k, v)
        else:
            instance = option
            displayer['current_option'] = [option.id]
        if not instance.on_change_with_has_beneficiary_clause():
            return
        displayer['option_name'] = instance.get_rec_name(None)
        # Make sure the instance will be editable
        instance.contract_status = 'quote'
        displayer['new_option'] = [model.dictionarize(instance,
                cls._option_fields_to_extract())]
        displayer['new_option'][0]['rec_name'] = instance.rec_name
        return displayer

    @classmethod
    def update_default_values(cls, wizard, base_endorsement, default_values):
        # Base_endorsement may be the current new endorsement. But we also have
        # to look in wizard.endorsement.contract_endorsements to detect other
        # contracts that may be modified
        if not base_endorsement.id:
            # New endorsement, no need to look somewhere else.
            all_endorsements = [base_endorsement]
        else:
            all_endorsements = list(wizard.endorsement.contract_endorsements)
        displayers, template = [], {}
        for endorsement in all_endorsements:
            updated_struct = endorsement.updated_struct
            template['contract'] = endorsement.contract.id
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                cls.update_dict(template, 'covered_element', covered_element)
                for option, o_values in values['options'].iteritems():
                    new_displayer = cls.create_displayer(option, template)
                    if new_displayer:
                        displayers.append(new_displayer)
        return {'options': displayers}

    def update_endorsement(self, base_endorsement, wizard):
        # Base_endorsement may be the current new endorsement. But we also have
        # to look in wizard.endorsement.contract_endorsements to detect other
        # contracts that may be modified
        if not base_endorsement.id:
            all_endorsements = {base_endorsement.contract.id: base_endorsement}
        else:
            all_endorsements = {x.contract.id: x
                for x in wizard.endorsement.contract_endorsements}
        pool = Pool()
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        OptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        BeneficiaryEndorsement = pool.get(
            'endorsement.contract.beneficiary')
        fields_to_extract = self._option_fields_to_extract()
        new_covered_elements, new_options, to_create = {}, {}, []
        for elem in self.options:
            cur_option = None
            if elem.current_option:
                cur_option = elem.current_option[0]
            new_values = model.dictionarize(elem.new_option[0],
                fields_to_extract)
            new_values.pop('contract_status', None)
            beneficiary_values = {x['party'] or x['reference']: x
                for x in new_values.pop('beneficiaries', [])}
            if not (elem.option_endorsement or cur_option.id in new_options):
                option_endorsement = OptionEndorsement(action='update',
                    option=cur_option.id, beneficiaries=[], values={})
                new_options[cur_option.id] = option_endorsement
                if not(elem.covered_element_endorsement or
                        elem.covered_element.id in new_covered_elements):
                    ce_endorsement = CoveredElementEndorsement(action='update',
                        options=[option_endorsement],
                        relation=elem.covered_element.id)
                    ctr_endorsement = all_endorsements[elem.contract.id]
                    if not ctr_endorsement.id:
                        ctr_endorsement.covered_elements = list(
                            ctr_endorsement.covered_elements) + [
                                ce_endorsement]
                    else:
                        ce_endorsement.contract_endorsement = \
                            ctr_endorsement.id
                    new_covered_elements[elem.covered_element.id] = \
                        ce_endorsement
                else:
                    ce_endorsement = (elem.covered_element_endorsement or
                        new_covered_elements[elem.covered_element.id])
                    if ce_endorsement.id:
                        option_endorsement.covered_element_endorsement = \
                            ce_endorsement.id
                    else:
                        ce_endorsement.options = list(
                            ce_endorsement.options) + [option_endorsement]
            else:
                option_endorsement = (elem.option_endorsement or
                    new_options[cur_option.id])
            option_endorsement.values.update(new_values)
            if cur_option is None:
                option_endorsement.benficiaries = [
                    BeneficiaryEndorsement(**benef_values)
                    for benef_values in beneficiary_values.itervalues()]
            else:
                current_beneficiaries = {
                    x.party.id if x.party else x.reference: x
                    for x in cur_option.beneficiaries}
                deleted = set(current_beneficiaries.keys()) - set(
                    beneficiary_values.keys())
                modified = set(current_beneficiaries.keys()) & set(
                    beneficiary_values.keys())
                created = set(beneficiary_values.keys()) - modified
                benef_endorsements = [BeneficiaryEndorsement(
                        action='remove', relation=current_beneficiaries[x].id)
                    for x in deleted] + [BeneficiaryEndorsement(
                        action='add', values=beneficiary_values[x])
                    for x in created]
                for party_id in modified:
                    beneficiary_instance = current_beneficiaries[party_id]
                    for k, v in beneficiary_values[party_id]:
                        setattr(beneficiary_instance, k, v)
                    update_values = beneficiary_instance._save_values
                    if update_values:
                        benef_endorsements.append(BeneficiaryEndorsement(
                                action='update',
                                relation=beneficiary_instance.id,
                                values=update_values))
                if option_endorsement.id:
                    [setattr(x, 'covered_option_endorsement',
                            option_endorsement.id)
                        for x in benef_endorsements]
                    to_create += benef_endorsements
                else:
                    option_endorsement.beneficiaries = benef_endorsements
        if to_create:
            BeneficiaryEndorsement.create([x._save_values for x in to_create])
        if new_options:
            OptionEndorsement.create([x._save_values
                    for x in new_options.itervalues()
                    if getattr(x, 'covered_element_endorsement', None)])
        if new_covered_elements:
            CoveredElementEndorsement.create([x._save_values
                    for x in new_covered_elements
                    if getattr(x, 'contract_endorsement', None)])


class StartEndorsement:
    __name__ = 'endorsement.start'

    manage_beneficiaries = StateView('endorsement.contract.beneficiary.manage',
        'endorsement_life.endorsement_contract_beneficiary_manage_view_form', [
            Button('Previous', 'manage_beneficiaries_previous',
                'tryton-go-previous'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'manage_beneficiaries_next', 'tryton-go-next')])
    manage_beneficiaries_previous = StateTransition()
    manage_beneficiaries_next = StateTransition()

    def default_manage_beneficiaries(self, name):
        ContractEndorsement = Pool().get('endorsement.contract')
        endorsement_part = self.get_endorsement_part_for_state(
            'manage_beneficiaries')
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            }
        endorsements = self.get_endorsements_for_state('manage_beneficiaries')
        if not endorsements:
            if self.select_endorsement.contract:
                endorsements = [ContractEndorsement(definition=self.definition,
                        endorsement=self.endorsement,
                        contract=self.select_endorsement.contract)]
            else:
                return result
        ManageBeneficiaries = Pool().get(
            'endorsement.contract.beneficiary.manage')
        result.update(ManageBeneficiaries.update_default_values(self,
                endorsements[0], result))
        return result

    def transition_manage_beneficiaries_next(self):
        self.end_current_part('manage_beneficiaries')
        return self.get_next_state('manage_beneficiaries')

    def transition_manage_beneficiaries_previous(self):
        self.end_current_part('manage_beneficiaries')
        return self.get_state_before('manage_beneficiaries')

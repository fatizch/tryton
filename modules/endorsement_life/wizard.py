from trytond.pyson import Eval, Len
from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import (EndorsementWizardStepMixin,
    add_endorsement_step)


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


class ManageBeneficiaries(EndorsementWizardStepMixin):
    'Manage Beneficiaries'

    __name__ = 'endorsement.contract.beneficiary.manage'

    options = fields.One2Many('endorsement.contract.beneficiary.manage.option',
        None, 'Options with Beneficiaries')

    @classmethod
    def view_attributes(cls):
        return super(ManageBeneficiaries, cls).view_attributes() + [
            ('/form/group[@id="one_option"]', 'states',
                {'invisible': Len(Eval('options', [])) != 1}),
            ('/form/group[@id="multiple_options"]', 'states',
                {'invisible': Len(Eval('options', [])) == 1}),
            ]

    @classmethod
    def state_view_name(cls):
        return 'endorsement_life.' \
            'endorsement_contract_beneficiary_manage_view_form'

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
                'reference', 'share', 'rec_name'],
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
                        instance.beneficiaries = list(
                            instance.beneficiaries) + [Beneficiary(
                                **beneficiary.values)]
                    elif beneficiary.action == 'remove':
                        old_beneficiaries.remove(beneficiary.beneficiary)
                    else:
                        old_beneficiaries.remove(beneficiary.beneficiary)
                        instance.beneficiaries = list(instance.beneficiaries) +\
                            [beneficiary.beneficiary]
                        for k, v in beneficiary.values.iteritems():
                            setattr(beneficiary.beneficiary, k, v)
        else:
            instance = option
            displayer['current_option'] = [option.id]
            displayer['option_endorsement'] = None
        if not instance.on_change_with_has_beneficiary_clause():
            return
        displayer['option_name'] = instance.get_rec_name(None)
        # Make sure the instance will be editable
        instance.contract_status = 'quote'
        displayer['new_option'] = [model.dictionarize(instance,
                cls._option_fields_to_extract())]
        displayer['new_option'][0]['rec_name'] = instance.rec_name
        return displayer

    def step_default(self, name):
        defaults = super(ManageBeneficiaries, self).step_default()
        contracts = self._get_contracts()
        displayers, template = [], {}
        for contract_id, endorsement in contracts.iteritems():
            updated_struct = endorsement.updated_struct
            template['contract'] = endorsement.contract.id
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                self.update_dict(template, 'covered_element', covered_element)
                for option, o_values in values['options'].iteritems():
                    new_displayer = self.create_displayer(option, template)
                    if new_displayer:
                        displayers.append(new_displayer)
        defaults['options'] = displayers
        return defaults

    def step_update(self):
        contracts = self._get_contracts()
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
                    ctr_endorsement = contracts[elem.contract.id]
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
                option_endorsement.beneficiaries = [
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
                    for k, v in beneficiary_values[party_id].iteritems():
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
                    for x in new_covered_elements.itervalues()
                    if getattr(x, 'contract_endorsement', None)])


class StartEndorsement:
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ManageBeneficiaries,
    'manage_beneficiaries')

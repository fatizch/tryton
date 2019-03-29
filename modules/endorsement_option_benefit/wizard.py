# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Len
from trytond.modules.coog_core import fields, model, utils
from trytond.modules.endorsement.wizard import (EndorsementWizardStepMixin,
    add_endorsement_step)


__all__ = [
    'OptionDisplayer',
    'StartEndorsement',
    'ManageOptionBenefits',
    'ManageOptionBenefitsDisplayer',
    ]


class OptionDisplayer(metaclass=PoolMeta):
    __name__ = 'contract.manage_options.option_displayer'

    @classmethod
    def _option_fields_to_extract(cls):
        fields = super(OptionDisplayer, cls)._option_fields_to_extract()
        Displayer = Pool().get('contract.manage_option_benefits.option')
        fields['contract.option.version'].append('benefits')
        fields['contract.option.benefit'] = \
            Displayer.get_option_benefit_fields()
        return fields


class ManageOptionBenefits(EndorsementWizardStepMixin):
    'Manage Benefits'

    __name__ = 'contract.manage_option_benefits'

    contract = fields.Many2One('endorsement.contract', 'Contract',
        domain=[('id', 'in', Eval('possible_contracts', []))],
        states={'invisible': Len(Eval('possible_contracts', [])) <= 1},
        depends=['possible_contracts'])
    possible_contracts = fields.Many2Many('endorsement.contract', None, None,
        'Possible Contracts')
    current_options = fields.One2Many('contract.manage_option_benefits.option',
        None, 'Options')
    all_options = fields.One2Many('contract.manage_option_benefits.option',
        None, 'Options')

    @classmethod
    def view_attributes(cls):
        return super(ManageOptionBenefits, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ]

    @classmethod
    def state_view_name(cls):
        return 'endorsement_option_benefit.' +\
            'endorsement_manage_option_benefits_view_form'

    @fields.depends('all_options', 'contract', 'current_options')
    def on_change_contract(self):
        self.update_all_options()
        self.update_current_options()

    def update_all_options(self):
        if not self.current_options:
            return
        new_options = list(self.current_options)
        for option in self.all_options:
            if option.contract == new_options[0].contract:
                continue
            new_options.append(option)
        self.all_options = new_options

    def update_current_options(self):
        new_options = []
        for option in self.all_options:
            if option.contract == self.contract.id:
                new_options.append(option)
        self.current_options = new_options

    def step_default(self, name):
        defaults = super(ManageOptionBenefits, self).step_default()
        possible_contracts = self.wizard.endorsement.contract_endorsements

        if not possible_contracts and self.wizard.select_endorsement.contract:
            contract_endorsement = Pool().get('endorsement.contract')(
                contract=self.wizard.select_endorsement.contract,
                endorsement=self.wizard.endorsement)
            contract_endorsement.save()
            possible_contracts = [contract_endorsement]

        defaults['possible_contracts'] = [x.id for x in possible_contracts]
        per_contract = {x: self.get_updated_options_from_contract(x)
            for x in possible_contracts}

        all_options = []
        for contract, options in per_contract.items():
            all_options += self.generate_displayers(contract, options)
        fields = self.get_displayer_fields()
        defaults['all_options'] = [model.dictionarize(x, fields)
            for x in all_options]
        if defaults['possible_contracts']:
            defaults['contract'] = defaults['possible_contracts'][0]
        return defaults

    def step_update(self):
        EndorsementContract = Pool().get('endorsement.contract')
        self.update_all_options()
        endorsement = self.wizard.endorsement
        per_contract = defaultdict(list)
        for option in self.all_options:
            per_contract[EndorsementContract(option.contract)].append(option)

        for contract, options in per_contract.items():
            utils.apply_dict(contract.contract, contract.apply_values())
            self.update_endorsed_options(contract, options)
            for covered_element in contract.contract.covered_elements:
                covered_element.options = list(covered_element.options)
            contract.contract.covered_elements = list(
                contract.contract.covered_elements)

        new_endorsements = []
        for contract_endorsement in list(per_contract.keys()):
            self._update_endorsement(contract_endorsement,
                contract_endorsement.contract._save_values)
            if not contract_endorsement.clean_up():
                new_endorsements.append(contract_endorsement)
        endorsement.contract_endorsements = new_endorsements
        endorsement.save()

    @classmethod
    def get_displayer_fields(cls):
        Displayer = Pool().get('contract.manage_option_benefits.option')
        return {
            'contract.manage_option_benefits.option': [
                'parent_name', 'parent', 'contract', 'option_id',
                'display_name', 'option_benefits', 'start_date'
                ],
            'contract.option.benefit': Displayer.get_option_benefit_fields() +
            ('available_deductible_rules', 'available_indemnification_rules',
                'available_revaluation_rules', 'contract_status')}

    @classmethod
    def get_version_fields(cls):
        Displayer = Pool().get('contract.manage_option_benefits.option')
        return {
            'contract.option.version': [
                'benefits', 'option', 'start', 'rec_name',
                'extra_data', 'extra_data_as_string',
                ],
            'contract.option.benefit': Displayer.get_option_benefit_fields() +
            ('available_deductible_rules', 'available_indemnification_rules',
                'available_revaluation_rules')}

    def get_updated_options_from_contract(self, contract_endorsement):
        contract = contract_endorsement.contract
        utils.apply_dict(contract, contract_endorsement.apply_values())
        return self.get_contract_options(contract)

    def get_contract_options(self, contract):
        return [x for covered in contract.covered_elements
            for x in covered.options
            if not x.id or x.is_active_at_date(self.effective_date)]

    def generate_displayers(self, contract_endorsement, options):
        pool = Pool()
        Option = pool.get('contract.manage_option_benefits.option')
        all_options = []
        for option in options:
            displayer = Option.new_displayer(option, self.effective_date)
            displayer.contract = contract_endorsement.id
            all_options.append(displayer)
        return all_options

    def update_endorsed_options(self, contract_endorsement, options):
        pool = Pool()
        Displayer = pool.get('contract.manage_option_benefits.option')
        options_per_key = {Displayer.get_parent_key(x): x
            for covered in contract_endorsement.contract.covered_elements
            for x in covered.options}
        for displayer in options:
            patched_option = options_per_key[displayer.parent]
            if patched_option.id and patched_option.id > 0:
                self._update_existing_option(patched_option, displayer)
            else:
                self._update_new_option(patched_option, displayer)

    def _update_existing_option(self, option, displayer):
        pool = Pool()
        Option = pool.get('contract.option')
        Version = pool.get('contract.option.version')

        fields = self.get_version_fields()
        fields['contract.option.version'].remove('start')
        fields['contract.option.version'].remove('rec_name')
        fields['contract.option.version'].remove('extra_data_as_string')
        contract = option.parent_contract
        original_version = Option(option.id).get_version_at_date(
            self.effective_date)
        original_values = model.dictionarize(original_version, fields)

        new_version = option.get_version_at_date(self.effective_date)
        if ((new_version.start or contract.initial_start_date) !=
                self.effective_date):
            new_version = Version(**original_values)

        new_version.benefits = displayer.option_benefits
        new_values = model.dictionarize(new_version, fields)

        if new_values != original_values:
            # Real modification, we update the option
            new_version.start = self.effective_date
            option.versions = [v for v in option.versions
                if not v.start or v.start < self.effective_date] + [
                new_version]
        else:
            # Clean up time. The 'apply_dict' from earlier could have left some
            # traces on versions
            if 'versions' in (option._values or {}):
                del option._values['versions']

    def _update_new_option(self, option, displayer):
        version = option.get_version_at_date(self.effective_date)
        assert version.start is None or version.start == self.effective_date
        version.benefits = displayer.option_benefits
        option.versions = [version]


class ManageOptionBenefitsDisplayer(model.CoogView):
    'Manage Benefit Options Displayer'

    __name__ = 'contract.manage_option_benefits.option'

    parent_name = fields.Char('Parent', readonly=True)
    parent = fields.Char('Parent', readonly=True)
    contract = fields.Integer('Contract', readonly=True)
    option_id = fields.Integer('Option', readonly=True)
    display_name = fields.Char('Option', readonly=True)
    option_benefits = fields.One2Many(
        'contract.option.benefit', None, 'Benefit')

    @classmethod
    def view_attributes(cls):
        return super(ManageOptionBenefitsDisplayer, cls).view_attributes() + [
            ("/form/group[@id='invisible_benefit']", 'states', {
                        'invisible': Len(Eval('option_benefits', [])) == 1})]

    @classmethod
    def new_displayer(cls, option, effective_date):
        pool = Pool()
        OptionBenefit = pool.get('contract.option.benefit')
        displayer = cls()
        displayer.parent_name = (
            option.covered_element or option.contract).rec_name
        displayer.parent = cls.get_parent_key(option)
        displayer.display_name = option.get_rec_name(None)
        displayer.option_id = getattr(option, 'id', None)
        version = option.get_version_at_date(effective_date)
        if not getattr(version, 'benefits', None):
            version.init_from_coverage(option.coverage)

        option_benefits = []
        for benefit in version.benefits:
            values = model.dictionarize(benefit)
            values.pop('version')
            values['contract_status'] = 'quote'
            option_benefits.append(OptionBenefit(**values))
            option_benefits[-1].on_change_benefit()
        displayer.option_benefits = option_benefits
        return displayer

    @classmethod
    def get_parent_key(cls, option):
        if option.id:
            return str(option)
        if option.covered_element:
            # This may cause some problems down the line :'(
            return str(option.covered_element.party)
        if option.contract:
            return str(option.contract)
        raise NotImplementedError

    @classmethod
    def get_option_benefit_fields(cls):
        return ('benefit', 'annuity_frequency', 'annuity_frequency_required',
            'deductible_rule', 'indemnification_rule', 'revaluation_rule',
            'indemnification_rule_extra_data', 'deductible_rule_extra_data',
            'revaluation_rule_extra_data')


class StartEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ManageOptionBenefits,
    'manage_option_benefits')

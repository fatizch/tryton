# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Len
from trytond.modules.cog_utils import fields, model, utils
from trytond.modules.endorsement import (EndorsementWizardStepMixin,
    add_endorsement_step)


__all__ = [
    'OptionDisplayer',
    'StartEndorsement',
    'ManageOptionBenefits',
    'ManageOptionBenefitsDisplayer',
    ]


class OptionDisplayer:
    __metaclass__ = PoolMeta
    __name__ = 'contract.manage_options.option_displayer'

    @classmethod
    def _option_fields_to_extract(cls):
        fields = super(OptionDisplayer, cls)._option_fields_to_extract()
        Displayer = Pool().get('contract.manage_option_benefits.option')
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
        for contract, options in per_contract.iteritems():
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

        for contract, options in per_contract.iteritems():
            utils.apply_dict(contract.contract, contract.apply_values())
            self.update_endorsed_options(contract, options)
            for covered_element in contract.contract.covered_elements:
                covered_element.options = list(covered_element.options)
            contract.contract.covered_elements = list(
                contract.contract.covered_elements)

        new_endorsements = []
        for contract_endorsement in per_contract.keys():
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
                'available_revaluation_rules')}

    @classmethod
    def get_version_fields(cls):
        Displayer = Pool().get('contract.manage_option_benefits.option')
        return {
            'contract.option.version': [
                'benefits', 'option', 'start', 'start_date', 'rec_name',
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
            for x in covered.options]

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
        Version = pool.get('contract.option.version')
        per_key = {Displayer.get_parent_key(x): x
            for covered in contract_endorsement.contract.covered_elements
            for x in covered.options}
        for displayer in options:
            patched_option = per_key[displayer.parent]
            version = patched_option.get_version_at_date(self.effective_date)
            if version.start == self.effective_date:
                patched_benefits = {x.benefit.id: x for x in version.benefits}
                for benefit in displayer.option_benefits:
                    patched_benefit = patched_benefits[benefit.benefit.id]
                    for fname in Displayer.get_option_benefit_fields():
                        new_value = getattr(benefit, fname, None)
                        old_value = getattr(patched_benefit, fname, None)
                        if new_value != old_value:
                            version.benefits = displayer.option_benefits
                            break
            else:
                fields = self.get_version_fields()
                version = Version(**model.dictionarize(version, fields))
                version.start = self.effective_date
                version.benefits = displayer.option_benefits
            patched_option.versions = [v for v in patched_option.versions
                if not v.start or v.start < self.effective_date] + [version]


class ManageOptionBenefitsDisplayer(model.CoopView):
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
        if getattr(version, 'benefits', None) is None:
            version.init_from_coverage(option.coverage)

        option_benefits = []
        for benefit in version.benefits:
            values = model.dictionarize(benefit)
            values.pop('version')
            option_benefits.append(OptionBenefit(**values))
            option_benefits[-1].on_change_benefit()
        displayer.option_benefits = option_benefits
        return displayer

    @classmethod
    def get_parent_key(cls, option):
        if option.id:
            return str(option)
        if option.covered_element:
            return str(option.covered_element.party)
        if option.contract:
            return str(option.contract)
        raise NotImplementedError

    @classmethod
    def get_option_benefit_fields(cls):
        return ('benefit',
            'deductible_rule', 'indemnification_rule', 'revaluation_rule',
            'indemnification_rule_extra_data',
            'deductible_rule_extra_data',
            'revaluation_rule_extra_data')


class StartEndorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ManageOptionBenefits,
    'manage_option_benefits')

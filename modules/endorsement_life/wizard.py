# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pyson import Eval, Len, If
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import model, fields, utils
from trytond.modules.endorsement.wizard import (EndorsementWizardStepMixin,
    add_endorsement_step)


__all__ = [
    'ManageBeneficiaries',
    'ManageBeneficiariesOptionDisplayer',
    'ManageBeneficiariesDisplayer',
    'StartEndorsement',
    ]


class ManageBeneficiaries(EndorsementWizardStepMixin):
    'Manage Beneficiaries'

    __name__ = 'contract.manage_beneficiaries'

    contract = fields.Many2One('endorsement.contract', 'Contract',
        domain=[('id', 'in', Eval('possible_contracts', []))],
        states={'invisible': Len(Eval('possible_contracts', [])) <= 1},
        depends=['possible_contracts'])
    possible_contracts = fields.Many2Many('endorsement.contract', None, None,
        'Possible Contracts')
    current_options = fields.One2Many('contract.manage_beneficiaries.option',
        None, 'Options')
    all_options = fields.One2Many('contract.manage_beneficiaries.option',
        None, 'Options')

    @classmethod
    def view_attributes(cls):
        return super(ManageBeneficiaries, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ]

    @classmethod
    def state_view_name(cls):
        return 'endorsement_life.' + \
            'endorsement_contract_beneficiary_manage_view_form'

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
        defaults = super(ManageBeneficiaries, self).step_default()
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
        defaults['all_options'] = [model.dictionarize(x) for x in all_options]
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
            utils.apply_dict(contract.contract,
                contract.apply_values())
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

    def update_endorsed_options(self, contract_endorsement, options):
        pool = Pool()
        Option = pool.get('contract.option')
        Displayer = pool.get('contract.manage_beneficiaries.option')
        per_key = {Displayer.get_parent_key(x): x
            for covered in contract_endorsement.contract.covered_elements
            for x in covered.options}
        for option in options:
            patched_option = per_key[option.parent]
            old_option = Option(option.option_id) if option.option_id else None

            patched_option.beneficiary_clause = option.beneficiary_clause
            patched_option.customized_beneficiary_clause = \
                option.customized_beneficiary_clause

            old_beneficiaries = {x.id: x
                for x in getattr(old_option, 'beneficiaries', [])}
            beneficiaries = []
            for displayer in option.beneficiaries:
                if displayer.action in ('nothing', 'modified'):
                    # Same behaviour for both cases since we need to rewrite
                    # the 'nothing' displayer in case they were previously
                    # modified
                    to_modify = old_beneficiaries[displayer.beneficiary_id]
                    for fname in Displayer.get_beneficiary_fields():
                        old_value = getattr(to_modify, fname, None)
                        new_value = getattr(displayer.beneficiary[0], fname,
                            None)
                        if old_value != new_value:
                            setattr(to_modify, fname, new_value)
                    beneficiaries.append(to_modify)
                elif displayer.action == 'added':
                    beneficiaries.append(displayer.beneficiary[0])

            patched_option.beneficiaries = beneficiaries

    def get_updated_options_from_contract(self, contract_endorsement):
        contract = contract_endorsement.contract
        utils.apply_dict(contract, contract_endorsement.apply_values())
        return self.get_contract_options(contract)

    def get_contract_options(self, contract):
        return [x for covered in contract.covered_elements
            for x in covered.options]

    def generate_displayers(self, contract_endorsement, options):
        pool = Pool()
        Option = pool.get('contract.manage_beneficiaries.option')
        all_options = []
        for option in options:
            if (not option.coverage.beneficiaries_clauses and
                    not option.beneficiaries):
                continue
            displayer = Option.new_displayer(option)
            displayer.contract = contract_endorsement.id
            all_options.append(displayer)
        return all_options


class ManageBeneficiariesOptionDisplayer(model.CoogView):
    'Manage Beneficiaries Option Displayer'

    __name__ = 'contract.manage_beneficiaries.option'

    parent_name = fields.Char('Parent', readonly=True)
    parent = fields.Char('Parent', readonly=True)
    contract = fields.Integer('Contract', readonly=True)
    option_id = fields.Integer('Option', readonly=True)
    display_name = fields.Char('Option', readonly=True)
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        readonly=True)
    beneficiary_clause_customizable = fields.Boolean(
        'Beneficiary Clause Customizable', readonly=True)
    beneficiary_clause = fields.Many2One('clause', 'Beneficiary Clause',
        states={'required': ~Eval('customized_beneficiary_clause')},
        domain=[('coverages', '=', Eval('coverage'))],
        depends=['coverage', 'customized_beneficiary_clause'])
    customized_beneficiary_clause = fields.Text(
        'Customized Beneficiary Clause',
        states={
            'required': ~Eval('beneficiary_clause'),
            'readonly': ~Eval('beneficiary_clause_customizable'),
            }, depends=['beneficiary_clause',
            'beneficiary_clause_customizable'],
        )
    beneficiaries = fields.One2Many(
        'contract.manage_beneficiaries.beneficiary', None, 'Beneficiaries')

    @fields.depends('beneficiary_clause', 'customized_beneficiary_clause')
    def on_change_beneficiary_clause(self):
        self.customized_beneficiary_clause = self.beneficiary_clause.content \
            if self.beneficiary_clause else ''
        self.beneficiary_clause_customizable = bool(self.beneficiary_clause and
            self.beneficiary_clause.customizable)

    @fields.depends('beneficiaries', 'option_id')
    def on_change_beneficiaries(self):
        if not self.option_id:
            return
        option = Pool().get('contract.option')(self.option_id)
        for beneficiary in self.beneficiaries:
            if beneficiary.beneficiary:
                beneficiary.beneficiary[0].option = option
                beneficiary.beneficiary = list(beneficiary.beneficiary)
        self.beneficiaries = list(self.beneficiaries)

    @classmethod
    def new_displayer(cls, option):
        pool = Pool()
        Option = pool.get('contract.option')
        Beneficiary = pool.get('contract.manage_beneficiaries.beneficiary')
        displayer = cls()
        displayer.parent_name = (option.covered_element
            or option.contract).rec_name
        displayer.parent = cls.get_parent_key(option)
        displayer.option_id = getattr(option, 'id', None)
        displayer.display_name = option.get_rec_name(None)
        displayer.coverage = option.coverage
        displayer.beneficiary_clause = getattr(option, 'beneficiary_clause',
            None)
        displayer.beneficiary_clause_customizable = displayer.beneficiary_clause and \
            displayer.beneficiary_clause.customizable
        displayer.customized_beneficiary_clause = getattr(option,
            'customized_beneficiary_clause', '')

        beneficiaries = []
        if displayer.option_id:
            old_option = Option(displayer.option_id)
            existing_beneficiaries = {x.id: x
                for x in old_option.beneficiaries}
        else:
            existing_beneficiaries = {}
        for beneficiary in getattr(option, 'beneficiaries', []):
            new_displayer = Beneficiary.init_from_beneficiary(beneficiary)
            if new_displayer.beneficiary_id:
                existing_beneficiaries.pop(new_displayer.beneficiary_id)
            beneficiaries.append(new_displayer)
        for removed in existing_beneficiaries.values():
            new_displayer = Beneficiary.init_from_beneficiary(removed)
            new_displayer.action = 'removed'
            beneficiaries.append(new_displayer)
        displayer.beneficiaries = beneficiaries
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
    def get_beneficiary_fields(cls):
        return ('accepting', 'address', 'party', 'reference', 'share')


class ManageBeneficiariesDisplayer(model.CoogView):
    'Manage Beneficiaries Displayer'

    __name__ = 'contract.manage_beneficiaries.beneficiary'

    beneficiary = fields.One2Many('contract.option.beneficiary', None,
        'Beneficiary', states={'readonly': Eval('action', '') == 'removed'})
    beneficiary_id = fields.Integer('Beneficiary Id', readonly=True)
    name = fields.Char('Name', readonly=True)
    action = fields.Selection([('nothing', ''), ('removed', 'Removed'),
        ('modified', 'Modified'), ('added', 'Added')], 'Action',
        domain=[If(Eval('action') == 'modified',
                ('action', 'in', ('modified', 'nothing')),
                If(Eval('action') == 'added',
                    ('action', 'in', ('added', 'removed')),
                    ('action', 'in', ('removed', 'nothing'))))],
        depends=['action'])

    @classmethod
    def default_action(cls):
        return 'added'

    @classmethod
    def default_beneficiary(cls):
        return [{}]

    @fields.depends('action', 'beneficiary', 'beneficiary_id', 'name')
    def on_change_action(self):
        pool = Pool()
        Beneficiary = pool.get('contract.option.beneficiary')
        OptionDisplayer = pool.get('contract.manage_beneficiaries.option')
        if self.beneficiary_id and self.action == 'nothing':
            old_version = Beneficiary(self.beneficiary_id)
            for fname in OptionDisplayer.get_beneficiary_fields():
                setattr(self.beneficiary[0], fname,
                    getattr(old_version, fname))
            self.beneficiary = list(self.beneficiary)
            self.name = self.beneficiary[0].on_change_with_rec_name()

    @fields.depends('action', 'beneficiary', 'beneficiary_id', 'name')
    def on_change_beneficiary(self):
        if not self.beneficiary:
            return
        self.name = self.beneficiary[0].on_change_with_rec_name()
        if not self.beneficiary_id or self.action == 'removed':
            return
        if self.value_changed():
            self.action = 'modified'
        else:
            self.action = 'nothing'

    def value_changed(self):
        pool = Pool()
        Beneficiary = pool.get('contract.option.beneficiary')
        OptionDisplayer = pool.get('contract.manage_beneficiaries.option')
        old_version = Beneficiary(self.beneficiary_id)
        for fname in OptionDisplayer.get_beneficiary_fields():
            old_value = getattr(old_version, fname, None)
            new_value = getattr(self.beneficiary[0], fname, None)
            if old_value != new_value:
                return True
        return False

    @classmethod
    def init_from_beneficiary(cls, beneficiary):
        pool = Pool()
        Beneficiary = pool.get('contract.option.beneficiary')
        OptionDisplayer = pool.get('contract.manage_beneficiaries.option')
        new_displayer = cls()
        new_displayer.beneficiary_id = getattr(beneficiary, 'id', None)
        fake_beneficiary = Beneficiary()
        for fname in OptionDisplayer.get_beneficiary_fields():
            setattr(fake_beneficiary, fname, getattr(beneficiary, fname, None))
        new_displayer.name = fake_beneficiary.on_change_with_rec_name()
        new_displayer.beneficiary = [fake_beneficiary]
        if new_displayer.beneficiary_id is None:
            new_displayer.action = 'added'
        else:
            if beneficiary._save_values:
                new_displayer.action = 'modified'
            else:
                new_displayer.action = 'nothing'
        return new_displayer


class StartEndorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ManageBeneficiaries,
    'manage_beneficiaries')

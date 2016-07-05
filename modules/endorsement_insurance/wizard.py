# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button
from trytond.pyson import Eval, Len, Bool, If, Equal
from trytond.model import Model

from trytond.modules.cog_utils import model, fields, utils, coop_date
from trytond.modules.endorsement import EndorsementWizardStepMixin, \
    add_endorsement_step

__metaclass__ = PoolMeta
__all__ = [
    'NewCoveredElement',
    'NewOptionOnCoveredElement',
    'ExtraPremiumDisplayer',
    'ManageExtraPremium',
    'ManageOptions',
    'OptionDisplayer',
    'RemoveOptionSelector',
    'ModifyCoveredElement',
    'CoveredElementDisplayer',
    'RemoveOption',
    'OptionSelector',
    'CoveredElementSelector',
    'NewExtraPremium',
    'VoidContract',
    'ManageExclusions',
    'ManageExclusionsOptionDisplayer',
    'ManageExclusionsDisplayer',
    'StartEndorsement',
    ]


class NewCoveredElement(EndorsementWizardStepMixin):
    'New Covered Element'

    __name__ = 'contract.covered_element.new'

    covered_elements = fields.One2Many('contract.covered_element', None,
        'New Covered Elements',
        domain=[
            # ('item_desc', '=', Eval('possible_item_desc', [])),
            ('parent', '=', None)],
        context={
            'contract': Eval('contract'),
            'product': Eval('product'),
            'start_date': Eval('start_date'),
            'all_extra_datas': Eval('extra_data')},
        depends=['contract', 'product', 'start_date', 'extra_data',
            'possible_item_desc'])
    extra_data = fields.Dict('extra_data', 'Contract Extra Data')
    extra_data_string = extra_data.translated('extra_data')
    contract = fields.Many2One('contract', 'Contract')
    possible_item_desc = fields.Many2Many('offered.item.description', None,
        None, 'Possible item desc')
    product = fields.Many2One('offered.product', 'Product')
    start_date = fields.Date('Start Date')

    def update_endorsement(self, endorsement, wizard):
        pool = Pool()
        EndorsementCoveredElementOption = pool.get(
            'endorsement.contract.covered_element.option')
        EndorsementCoveredElementVersion = pool.get(
            'endorsement.contract.covered_element.version')
        wizard.update_add_to_list_endorsement(self, endorsement,
            'covered_elements')
        endorsement.save()
        vlist_options = []
        vlist_versions = []
        for i, covered_element in enumerate(self.covered_elements):
            for option in covered_element.options:
                template = {
                    'action': 'add',
                    'values': {},
                    'covered_element_endorsement':
                        endorsement.covered_elements[i],
                }
                for field in self.endorsement_part.option_fields:
                    new_value = getattr(option, field.name, None)
                    if isinstance(new_value, Model):
                        new_value = new_value.id
                    template['values'][field.name] = new_value
                    template['values']['manual_start_date'] = \
                        wizard.endorsement.effective_date
                    if 'start_date' in template['values']:
                        template['values'].pop('start_date')
                vlist_options.append(template)
            for version in covered_element.versions:
                vlist_versions.append({
                        'action': 'add',
                        'values': {'start': version.start},
                        'extra_data': version.extra_data,
                        'covered_element_endorsement':
                        endorsement.covered_elements[i],
                        })
        EndorsementCoveredElementOption.create(vlist_options)
        EndorsementCoveredElementVersion.create(vlist_versions)


class RemoveOption(EndorsementWizardStepMixin):

    'Remove Option'

    __name__ = 'contract.covered_element.option.remove'

    @classmethod
    def __setup__(cls):
        super(RemoveOption, cls).__setup__()
        cls._error_messages.update({
                'must_end_all_options': 'All options on a covered element must'
                ' be removed if a mandatory option is removed',
                'cannot_end_all_covered_elements': 'You cannot remove all'
                ' options on all covered elements of a contract. You may want'
                ' to end the contract instead.',
                'end_date_anterior_to_start_date': 'You are setting an end'
                ' date anterior to start date for option : "%s"',
                'voiding': 'You are voiding an option.',
                'at_start_date_no_void': 'You are ending an option the day'
                ' it starts. Are you sure you want to have an option lasting'
                ' only one day and not void it ?',
                })

    options = fields.One2Many(
        'contract.covered_element.option.remove.option_selector', None,
        'Options To Remove')

    @classmethod
    def update_default_values(cls, wizard, base_endorsement, default_values):
        if not base_endorsement.id:
            all_endorsements = [base_endorsement]
        else:
            all_endorsements = list(wizard.endorsement.contract_endorsements)
        effective_date = wizard.select_endorsement.effective_date
        selectors = []
        for endorsement in all_endorsements:
            template = {
                'contract': endorsement.contract.id,
                'action': '',
                'covered_element_endorsement': None,
                'option_endorsement': None,
                'covered_element_option_endorsement': None,
                'effective_date': endorsement.endorsement.effective_date}
            updated_struct = endorsement.updated_struct
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                for option in values['options']:
                    selector = template.copy()
                    if not option.__name__ ==\
                            'endorsement.contract.covered_element.option':
                        selector.update({
                                'covered_element': option.covered_element.id,
                                'option': option.id,
                                'start_date': option.start_date,
                                'end_date': option.end_date,
                                'sub_status':
                                option.sub_status.id if option.sub_status
                                else None,
                                })
                    else:
                        real_option = option.option
                        selector.update({
                                'covered_element':
                                        covered_element.relation,
                                'option': option.relation,
                                'start_date': real_option.start_date,
                                'end_date': option.values['manual_end_date'],
                                'sub_status':
                                    option.values['sub_status'],
                                'covered_element_endorsement':
                                    option.covered_element_endorsement.id,
                                'action': option.values.get('status', ''),
                                'covered_element_option_endorsement':
                                    option.id,
                                })
                    selectors.append(selector)
            for option in updated_struct['options']:
                selector = None
                if not hasattr(option, 'get_endorsed_record'):
                    if option.coverage.subscription_behaviour != 'mandatory':
                        selector = template.copy()
                        selector.update({'covered_element': None,
                                'option': option.id,
                                'start_date': option.start_date,
                                'end_date': option.end_date,
                                'sub_status':
                                    option.sub_status.id if option.sub_status
                                    else None,
                                })
                else:
                    selector = template.copy()
                    real_option = option.option
                    selector.update({'covered_element': None,
                            'option': option.relation,
                            'start_date': real_option.start_date,
                            'end_date': option.values['manual_end_date'],
                            'sub_status':
                            option.values['sub_status'],
                            'action': option.values.get('status', ''),
                            'option_endorsement': option.id,
                            })
                if selector:
                    selectors.append(selector)

        return {'options': selectors, 'effective_date': effective_date}

    def update_endorsement(self, base_endorsement, wizard):
        effective_date = wizard.select_endorsement.effective_date
        if not base_endorsement.id:
            all_endorsements = {base_endorsement.contract.id:
                base_endorsement}
        else:
            all_endorsements = {x.contract.id: x
                for x in wizard.endorsement.contract_endorsements}
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        OptionEndorsement = pool.get('endorsement.contract.option')
        CovOptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        endorsed_cov_options_per_contract = defaultdict(list)
        for endorsement in all_endorsements.values():
            op_endorsement_to_delete = []
            cov_endorsement_to_delete = []
            updated_struct = endorsement.updated_struct
            ce_endorsements = {x.relation: x for x in
                updated_struct['covered_elements'] if hasattr(x, 'relation')}
            for option in self.options:
                covered_element = option.covered_element

                if option.covered_element and option.action and not \
                        option.covered_element_endorsement:
                    if option.covered_element.id not in ce_endorsements:
                        ce_endorsements[covered_element.id] = \
                            CoveredElementEndorsement(
                                contract_endorsement=endorsement,
                                action='update', options=[],
                                relation=covered_element.id)
                        option.covered_element_endorsement = \
                            ce_endorsements[covered_element.id]
                        ce_endorsements[covered_element.id].save()

                if option.covered_element and not option.action and \
                        option.covered_element_option_endorsement:
                    CovOptionEndorsement.delete(
                        [option.covered_element_option_endorsement])
                    if len(CoveredElementEndorsement(
                            option.covered_element_endorsement).options) == 0:
                        cov_endorsement_to_delete.append(
                            option.covered_element_endorsement)

                if not option.covered_element and not option.action and \
                        option.option_endorsement:
                    op_endorsement_to_delete.append(option.option_endorsement)

                if not option.covered_element and option.action and \
                        option.option_endorsement:
                    # This is a temporary measure to get around the clean_up
                    # method deleting the OptionEndorsement
                    OptionEndorsement.delete([option.option_endorsement])
                    OptionEndorsement.create([{
                            'relation': option.option.id,
                            'values': {'manual_end_date': effective_date,
                                    'sub_status': option.sub_status.id if
                                    option.sub_status else None,
                                    'status': option.action},
                            'action': 'update',
                            'definition': self.endorsement_definition,
                            'contract_endorsement': endorsement.id,
                            }])
                if option.covered_element and option.action and \
                    option.covered_element_option_endorsement and \
                        option.covered_element_endorsement:
                    option.covered_element_option_endorsement.values[
                        'sub_status'] = option.sub_status.id
                    option.covered_element_option_endorsement.values[
                        'status'] = option.action

            vlist_cov_opt = [{
                    'covered_element_endorsement': ce_endorsements[
                        x.covered_element.id],
                    'relation': x.option.id,
                    'definition': self.endorsement_definition,
                    'values': {'manual_end_date': effective_date,
                        'sub_status': x.sub_status.id if x.sub_status
                        else None,
                        'status': x.action},
                    'action': 'update'}
                for x in self.options if (x.action and not
                    x.covered_element_option_endorsement and
                    x.covered_element)]
            vlist_opt = [{
                    'relation': x.option.id,
                    'definition': self.endorsement_definition,
                    'contract_endorsement': endorsement,
                    'values': {'manual_end_date': effective_date,
                        'sub_status': x.sub_status.id if x.sub_status
                        else None,
                        'status': x.action},
                    'action': 'update'}
                for x in self.options if (x.action and not
                    x.option_endorsement and not
                    x.covered_element)]

            OptionEndorsement.create(vlist_opt)
            CovOptionEndorsement.create(vlist_cov_opt)
            OptionEndorsement.delete(op_endorsement_to_delete)
            CoveredElementEndorsement.delete(cov_endorsement_to_delete)

            # Only end mandatory option if all options on covered_element
            # are also ended
            for ce_id, ce_endorsement in ce_endorsements.iteritems():
                if [x for x in ce_endorsement.options if
                        (x.option.coverage.subscription_behaviour ==
                            'mandatory')]:
                    if (set([x.option for x in ce_endorsement.options]) !=
                            set(CoveredElement(ce_id).options)):
                        self.raise_user_error('must_end_all_options')
                if ce_endorsement.options:
                    endorsed_cov_options_per_contract[
                        ce_endorsement.contract_endorsement.contract].extend(
                        [x.option for x in ce_endorsement.options])

        cov_options_per_contract = defaultdict(list)
        for contract_endorsement in all_endorsements.values():
            for covered_elem in contract_endorsement.contract.covered_elements:
                cov_options_per_contract[contract_endorsement.contract].extend(
                    covered_elem.options)

        for contract, options in endorsed_cov_options_per_contract.iteritems():
            if set(cov_options_per_contract[contract]) == set(options):
                self.raise_user_error('cannot_end_all_covered_elements')
            for option in options:
                if option.start_date > effective_date:
                    self.raise_user_error('end_date_anterior_to_start_date',
                        (option.rec_name))

        if any(option.action == 'void' for option in self.options):
            self.raise_user_warning('Voiding', 'voiding')
        if any(option.start_date == effective_date and
                option.action and option.action != 'void' for
                option in self.options):
            self.raise_user_warning('at_start_date_no_void',
                'at_start_date_no_void')

        for cov in base_endorsement.covered_elements:
            for opt in cov.options:
                opt.values = opt.values
            cov.options = cov.options

        base_endorsement.covered_elements = base_endorsement.covered_elements
        base_endorsement.save()


class RemoveOptionSelector(model.CoopView):
    'Remove Option Selector'

    __name__ = 'contract.covered_element.option.remove.option_selector'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    option = fields.Many2One('contract.option', 'Option', readonly=True)
    covered_element_option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option',
        'Covered Element Option Endorsement', readonly=True)
    option_endorsement = fields.Many2One(
        'endorsement.contract.option', 'Option Endorsement', readonly=True)
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', readonly=True)
    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Covered Element',
        readonly=True)
    action = fields.Selection([('', ''), ('terminated', 'Terminate'),
            ('void', 'Void')], 'Action',
        domain=[If((Equal(Eval('start_date'), Eval('effective_date'))),
                ('action', 'in', ['terminated', 'void', '']),
                ('action', '!=', 'void'))],
        depends=['start_date', 'effective_date'])
    start_date = fields.Date('Start Date', readonly=True)
    end_date = fields.Date('End Date',
        states={'required': Bool(Eval('action'))},
        depends=['action'], readonly=True)
    sub_status = fields.Many2One('contract.sub_status',
        'Sub Status', states={'required': Bool(Eval('action'))},
        domain=[('status', '=', Eval('action'))],
        depends=['action'])
    effective_date = fields.Date('Effective Date', readonly=True)

    @classmethod
    def view_attributes(cls):
        return super(RemoveOptionSelector, cls).view_attributes() + [
            ('/tree', 'colors', If(Eval('action', False),
                    'red', 'black')),
            ]


class NewOptionOnCoveredElement(EndorsementWizardStepMixin):
    'New Covered Element Option'

    __name__ = 'contract.covered_element.add_option'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', states={
            'invisible': Len(Eval('possible_covered_elements', [])) > 1,
            },
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        depends=['possible_covered_elements'])
    existing_options = fields.Many2Many('contract.option', None, None,
        'Existing Options', states={
            'readonly': True,
            'invisible': ~Eval('covered_element', False)},
        depends=['covered_element'])
    new_options = fields.One2Many('contract.option', None, 'New Options',
        states={'invisible': ~Eval('covered_element', False)},
        domain=[('coverage', 'in', Eval('possible_coverages'))],
        depends=['possible_coverages', 'covered_element'])
    possible_coverages = fields.Many2Many('offered.option.description',
        None, None, 'Possible Coverages')
    possible_covered_elements = fields.Many2Many('contract.covered_element',
        None, None, 'Possible Covered Elements', states={'invisible': True})

    @fields.depends('covered_element', 'new_options', 'effective_date')
    def on_change_covered_element(self):
        if not self.covered_element:
            self.new_options = []
            self.possible_coverages = []
            self.existing_options = []
            return
        Coverage = Pool().get('offered.option.description')
        self.existing_options = [x for x in self.covered_element.options]
        self.possible_coverages = list(
            set([x for x in Coverage.search(
                        Coverage.get_possible_coverages_clause(
                            self.covered_element, self.effective_date))]) -
            set([x.coverage for x in self.covered_element.options]))

    def update_option(self, option):
        contract = self.covered_element.contract
        option.covered_element = self.covered_element
        option.product = contract.product
        option.start_date = self.effective_date
        option.appliable_conditions_date = contract.appliable_conditions_date
        option.all_extra_datas = self.covered_element.all_extra_datas
        option.status = 'quote'
        option.contract_status = 'quote'

    @fields.depends('covered_element', 'new_options', 'effective_date')
    def on_change_new_options(self):
        for elem in self.new_options:
            self.update_option(elem)
        self.new_options = self.new_options

    @classmethod
    def view_attributes(cls):
        return super(NewOptionOnCoveredElement, cls).view_attributes() + [
            ('/form/group[@id="hidden"]', 'states', {'invisible': True}),
        ]

    @classmethod
    def update_default_values(cls, wizard, endorsement, default_values):
        modified_covered_elements = [x for x in endorsement.covered_elements
            if x.action in ('add', 'update')]
        if not modified_covered_elements:
            return {}
        if len(modified_covered_elements) != 1:
            # TODO
            raise NotImplementedError
        covered_element = modified_covered_elements[0].covered_element
        update_dict = {
            'covered_element': covered_element.id,
            'new_options': [dict({'start_date': x.values.get(
                            'manual_start_date', None)}, **x.values)
                for x in modified_covered_elements[0].options
                if x.action == 'add'],
            }
        return update_dict

    def update_endorsement(self, endorsement, wizard):
        pool = Pool()
        EndorsementCoveredElement = pool.get(
            'endorsement.contract.covered_element')
        EndorsementCoveredElementOption = pool.get(
            'endorsement.contract.covered_element.option')
        good_endorsement = [x for x in endorsement.covered_elements
            if x.covered_element == self.covered_element]
        if not good_endorsement:
            good_endorsement = EndorsementCoveredElement(
                contract_endorsement=endorsement,
                relation=self.covered_element.id,
                definition=self.endorsement_definition,
                options=[],
                action='update',
                )
        else:
            good_endorsement = good_endorsement[0]
        option_endorsements = dict([(x.coverage, x)
                for x in good_endorsement.options
                if x.action == 'add' and 'coverage' in x.values])
        new_option_endorsements = [x for x in good_endorsement.options
            if x.action != 'add']
        for new_option in self.new_options:
            if new_option.coverage in option_endorsements:
                option_endorsement = option_endorsements[new_option.coverage]
                new_option_endorsements.append(option_endorsement)
                del option_endorsements[new_option.coverage]
            else:
                option_endorsement = EndorsementCoveredElementOption(
                    action='add', values={})
                new_option_endorsements.append(option_endorsement)
            new_option.manual_start_date = new_option.start_date
            for field in self.endorsement_part.option_fields:
                new_value = getattr(new_option, field.name, None)
                if isinstance(new_value, Model):
                    new_value = new_value.id
                option_endorsement.values[field.name] = new_value
        EndorsementCoveredElementOption.delete(option_endorsements.values())
        good_endorsement.options = new_option_endorsements

        good_endorsement.save()


class ModifyCoveredElement(EndorsementWizardStepMixin):
    'Modify Covered Element'

    __name__ = 'contract.covered_element.modify'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    current_parent = fields.Selection('get_possible_parents',
        'Parent')
    all_covered = fields.One2Many('contract.covered_element.modify.displayer',
        None, 'All Covered Elements')
    current_covered = fields.One2Many(
        'contract.covered_element.modify.displayer', None,
        'Current Covered Elements')
    possible_parents = fields.Text('Possible Parents', readonly=True)

    @classmethod
    def view_attributes(cls):
        return super(ModifyCoveredElement, cls).view_attributes() + [(
                '/form/group[@id="invisible"]',
                'states',
                {'invisible': True})]

    @property
    def _parent(self):
        if not getattr(self, 'current_parent', None):
            return None
        parent_model, parent_id = self.current_parent.split(',')
        return Pool().get(parent_model)(int(parent_id))

    @fields.depends('possible_parents')
    def get_possible_parents(self):
        if not self.possible_parents:
            return []
        return [tuple(x.split('|', 1))
            for x in self.possible_parents.split('\n')]

    @fields.depends('all_covered', 'contract', 'current_covered',
        'current_parent', 'effective_date')
    def on_change_current_parent(self):
        self.update_contract()
        self.update_all_covered()
        self.update_current_covered()

    def calculate_possible_parents(self):
        return list(self.wizard.endorsement.contract_endorsements)

    def update_contract(self):
        if isinstance(self._parent, Pool().get('endorsement.contract')):
            self.contract = self._parent.contract
        else:
            raise NotImplementedError

    def update_all_covered(self):
        if not self.current_covered:
            return
        new_covered_elements = list(self.current_covered)
        for covered_element in self.all_covered:
            if covered_element.parent == new_covered_elements[0].parent:
                continue
            new_covered_elements.append(covered_element)
        self.all_covered = new_covered_elements

    def update_current_covered(self):
        new_covered_elements = []
        for covered_element in sorted(self.all_covered,
                key=lambda x: x.party.name if x.party else ''):
            if covered_element.parent == self.current_parent:
                new_covered_elements.append(covered_element)
        self.current_covered = new_covered_elements

    def step_default(self, field_names):
        defaults = super(ModifyCoveredElement, self).step_default()
        possible_parents = self.calculate_possible_parents()
        defaults['possible_parents'] = '\n'.join(
            [str(x) + '|' + self.get_parent_name(x) for x in possible_parents])
        per_parent = {x: self.get_covered_from_parent(x)
            for x in possible_parents}

        all_covered = []
        for possible_parent, covered_elements in per_parent.iteritems():
            for covered_element in covered_elements:
                all_covered += self.generate_displayers(possible_parent,
                    covered_element)
        defaults['all_covered'] = [x._changed_values for x in all_covered]
        if defaults['all_covered']:
            defaults['current_parent'] = defaults['all_covered'][0]['parent']
        return defaults

    def step_update(self):
        self.update_all_covered()
        endorsement = self.wizard.endorsement
        per_parent = defaultdict(list)
        for covered_element in self.all_covered:
            per_parent[covered_element.parent].append(covered_element)

        contract_endorsements = {}
        for contract_endorsement in endorsement.contract_endorsements:
            contract = contract_endorsement.contract
            utils.apply_dict(contract, contract_endorsement.apply_values())
            contract_endorsements[contract.id] = contract

        for parent, new_covered_elements in per_parent.iteritems():
            self.current_parent = parent
            parent = self.get_parent_endorsed(self._parent,
                contract_endorsements)
            self.update_endorsed_covered(new_covered_elements, parent)
            parent.covered_elements = list(parent.covered_elements)

        new_endorsements = []
        for contract_endorsement in endorsement.contract_endorsements:
            self._update_endorsement(contract_endorsement,
                contract_endorsement.contract._save_values)
            if not contract_endorsement.clean_up():
                new_endorsements.append(contract_endorsement)
        endorsement.contract_endorsements = new_endorsements

    def get_parent_endorsed(self, parent, contract_endorsements):
        if isinstance(parent, Pool().get('endorsement.contract')):
            return contract_endorsements[parent.contract.id]
        else:
            raise NotImplementedError

    def update_endorsed_covered(self, new_covered_elements, parent):
        per_id = {x.id: x for x in parent.covered_elements}
        for new_covered in new_covered_elements:
            if new_covered.action == 'nothing':
                self._update_nothing(new_covered, parent, per_id)
            elif new_covered.action == 'modified':
                self._update_modified(new_covered, parent, per_id)

    def cancel_versions_changes(self, new_covered_element, per_id):
        CoveredElement = Pool().get('contract.covered_element')
        prev_covered = CoveredElement(new_covered_element.cur_covered_id)
        covered = per_id[new_covered_element.cur_covered_id]
        covered.versions = prev_covered.versions

    def _update_nothing(self, new_covered_element, parent, per_id):
        # Cancel modifications
        assert new_covered_element.cur_covered_id
        self.cancel_versions_changes(new_covered_element, per_id)

    def _update_modified(self, new_covered_element, parent, per_id):
        assert new_covered_element.cur_covered_id
        good_covered = per_id[new_covered_element.cur_covered_id]
        if not new_covered_element.check_versions_modified():
            self.cancel_versions_changes(new_covered_element, per_id)
            return
        new_versions = sorted([v for v in good_covered.versions
                if not v.start or
                v.start <= new_covered_element.effective_date],
            key=lambda x: x.start or datetime.date.min)
        current_version = new_versions[-1]
        if not current_version.start or (current_version.start !=
                new_covered_element.effective_date):
            current_version = new_covered_element.to_version(
                previous_version=new_versions[-1])
            new_versions.append(current_version)
        else:
            current_version.extra_data = new_covered_element.extra_data
        good_covered.versions = new_versions

    def get_covered_from_parent(self, parent):
        if isinstance(parent, Pool().get('endorsement.contract')):
            contract = parent.contract
            utils.apply_dict(contract, parent.apply_values())
            return contract.covered_elements
        else:
            raise NotImplementedError

    def generate_displayers(self, parent, covered_element):
        Displayer = Pool().get('contract.covered_element.modify.displayer')
        save_values = covered_element._save_values
        displayer = Displayer.new_displayer(covered_element,
            self.effective_date)
        displayer.parent = str(parent)
        displayer.parent_rec_name = self.get_parent_name(parent)
        if not save_values:
            # Not modified covered
            displayer.action = 'nothing'
        elif covered_element.id:
            # covered existed before, either modification or resiliation
            version_date = covered_element.get_version_at_date(
                self.effective_date).start
            if not version_date or version_date == self.effective_date:
                displayer.action = 'modified'
            else:
                # Only covered, resiliation
                displayer.action = 'nothing'
        return [displayer]

    def get_parent_name(self, parent):
        if isinstance(parent, Pool().get('endorsement.contract')):
            return parent.contract.rec_name
        else:
            return parent.rec_name

    @classmethod
    def state_view_name(cls):
        return 'endorsement_insurance.' + \
            'contract_modify_covered_element_view_form'


class CoveredElementDisplayer(model.CoopView):
    'Covered Element Displayer'

    __name__ = 'contract.covered_element.modify.displayer'

    action = fields.Selection([('nothing', ''), ('modified', 'Modified')],
        'Action')
    parent = fields.Char('Parent Reference', readonly=True)
    parent_rec_name = fields.Char('Parent', readonly=True)
    extra_data = fields.Dict('extra_data', 'Extra Data', states={
            'invisible': ~Eval('extra_data')})
    extra_data_as_string = fields.Text('Extra Data', readonly=True, states={
            'invisible': ~Eval('extra_data')})
    display_name = fields.Char('Name', readonly=True)
    cur_covered_id = fields.Integer('Existing Covered Element', readonly=True)
    effective_date = fields.Date('Effective Date', readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)

    @property
    def _parent(self):
        if hasattr(self, '__parent'):
            return self.__parent
        if not getattr(self, 'parent', None):
            self.__parent = None
            return None
        parent_model, parent_id = self.parent.split(',')
        self.__parent = Pool().get(parent_model)(int(parent_id))
        return self.__parent

    @fields.depends('action', 'cur_covered_id', 'effective_date', 'extra_data',
        'extra_data_as_string')
    def on_change_action(self):
        pool = Pool()
        if self.cur_covered_id and self.action == 'nothing':
            self.extra_data = pool.get('contract.covered_element')(
                self.cur_covered_id).get_version_at_date(
                self.effective_date).extra_data
        self.update_extra_data_string()

    @fields.depends('action', 'cur_covered_id', 'effective_date',
        'extra_data', 'extra_data_as_string')
    def on_change_extra_data(self):
        self.update_extra_data_string()
        if self.check_modified():
            self.action = 'modified'
        else:
            self.action = 'nothing'

    def check_versions_modified(self):
        previous_extra_data = Pool().get('contract.covered_element')(
            self.cur_covered_id).get_version_at_date(
            self.effective_date).extra_data
        return self.extra_data != previous_extra_data

    def check_modified(self):
        if not self.cur_covered_id:
            return True
        return self.check_versions_modified()

    def update_extra_data_string(self):
        self.extra_data_as_string = Pool().get(
            'extra_data').get_extra_data_summary([self], 'extra_data')[self.id]

    @classmethod
    def new_displayer(cls, covered_element, effective_date):
        displayer = cls()
        displayer.effective_date = effective_date
        if getattr(covered_element, 'id', None):
            displayer.cur_covered_id = covered_element.id
            displayer.display_name = covered_element.rec_name
        else:
            displayer.cur_covered_id = None
            displayer.display_name = 'New Covered Element (%s)' % (
                covered_element.party.rec_name)
        if getattr(covered_element, 'versions', None) is None:
            covered_element.versions = [Pool().get(
                    'contract.covered_element.version').get_default_version()]
        displayer.action = 'nothing'
        displayer.extra_data = covered_element.get_version_at_date(
            effective_date).extra_data
        displayer.party = covered_element.party
        return displayer

    def to_version(self, previous_version=None):
        Version = Pool().get('contract.covered_element.version')
        if previous_version is None:
            version = Version(start=None)
        else:
            version = Version(**model.dictionarize(previous_version,
                    self._covered_element_fields_to_extract()))
            version.start = self.effective_date
        version.extra_data = self.extra_data
        return version

    @classmethod
    def _covered_element_fields_to_extract(cls):
        return {
            'contract.covered_element': [],
            'contract.covered_element.version': ['extra_data'],
            }


class ExtraPremiumDisplayer(model.CoopView):
    'Extra Premium Displayer'

    __name__ = 'endorsement.contract.extra_premium.displayer'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', readonly=True)
    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Covered Element',
        readonly=True)
    covered_element_name = fields.Char('Covered Element', readonly=True)
    option = fields.Many2One('contract.option', 'Option', readonly=True)
    option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option', 'Option Endorsement',
        readonly=True)
    option_name = fields.Char('Option', readonly=True)
    extra_premium = fields.One2Many('contract.option.extra_premium',
        None, 'Extra Premium', states={'readonly': ~Eval('to_add')},
        depends=['to_add'])
    extra_premium_id = fields.Integer('Extra Premium Id')
    extra_premium_name = fields.Char('Extra Premium', readonly=True)
    to_delete = fields.Boolean('To Delete')
    to_add = fields.Boolean('To Add')

    @classmethod
    def view_attributes(cls):
        return super(ExtraPremiumDisplayer, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ('/tree', 'colors', If(Eval('to_delete', False), 'red',
                    If(Eval('to_add', False), 'green', 'grey'))),
            ]


class ManageExtraPremium(EndorsementWizardStepMixin):
    'Manage Extra Premium'

    __name__ = 'endorsement.contract.manage_extra_premium'

    extra_premiums = fields.One2Many(
        'endorsement.contract.extra_premium.displayer', None, 'Extra Premiums')

    @classmethod
    def view_attributes(cls):
        return super(ManageExtraPremium, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states', {'invisible': True}),
        ]

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
    def _extra_premium_fields_to_extract(cls):
        return ['calculation_kind', 'capital_per_mil_rate', 'currency',
            'currency_digits', 'currency_symbol', 'duration', 'duration_unit',
            'end_date', 'flat_amount', 'is_discount', 'max_rate',
            'max_value', 'motive', 'option', 'rate', 'start_date',
            'flat_amount_frequency']

    @classmethod
    def create_displayer(cls, extra_premium, template):
        ExtraPremium = Pool().get('contract.option.extra_premium')
        displayer = template.copy()
        if extra_premium.__name__ == 'endorsement.contract.extra_premium':
            if extra_premium.action == 'add':
                instance = ExtraPremium(**extra_premium.values)
                displayer['extra_premium_id'] = None
                displayer['to_add'] = True
            elif extra_premium.action == 'update':
                instance = extra_premium.extra_premium
                displayer['extra_premium_id'] = instance.id
                displayer['to_delete'] = True
        else:
            instance = extra_premium
            displayer['extra_premium_id'] = extra_premium.id
        instance.currency = template['currency']
        displayer['extra_premium_name'] = '%s %s' % (
            instance.get_value_as_string(None), instance.motive.name)
        displayer['extra_premium'] = [model.dictionarize(instance,
                cls._extra_premium_fields_to_extract())]
        displayer['extra_premium'][0]['option'] = template['fake_option']
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
        displayers, template = [], {'to_add': False, 'to_delete': False}
        # Set fake option to bypass required rule
        contract = all_endorsements[0].contract
        template['fake_option'] = (contract.options +
            contract.covered_element_options)[0].id
        template['currency'] = contract.currency.id
        for endorsement in all_endorsements:
            updated_struct = endorsement.updated_struct
            template['contract'] = endorsement.contract.id
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                cls.update_dict(template, 'covered_element', covered_element)
                for option, o_values in values['options'].iteritems():
                    cls.update_dict(template, 'option', option)
                    for extra_premium, ex_values in (
                            o_values['extra_premiums'].iteritems()):
                        displayers.append(cls.create_displayer(extra_premium,
                                template))
        return {'extra_premiums': displayers}

    def update_endorsement(self, base_endorsement, wizard):
        # Base_endorsement may be the current new endorsement. But we also have
        # to look in wizard.endorsement.contract_endorsements to detect other
        # contracts that may be modified
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        OptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        ExtraPremiumEndorsement = pool.get(
            'endorsement.contract.extra_premium')
        if not base_endorsement.id:
            all_endorsements = {base_endorsement.contract.id: base_endorsement}
        else:
            all_endorsements = {x.contract.id: x
                for x in wizard.endorsement.contract_endorsements}
        for endorsement in all_endorsements.values():
            for covered_endorsement in endorsement.covered_elements:
                for option_endorsement in covered_endorsement.options:
                    option_endorsement.extra_premiums = []
                covered_endorsement.options = list(covered_endorsement.options)
            endorsement.covered_elements = list(endorsement.covered_elements)
            endorsement.save()
        new_covered_elements, new_options, to_create = {}, {}, []
        for elem in self.extra_premiums:
            if elem.to_delete:
                if elem.extra_premium_id:
                    ex_endorsement = ExtraPremiumEndorsement(action='update',
                        extra_premium=elem.extra_premium_id,
                        values={'manual_end_date': coop_date.add_day(
                                self.effective_date, -1)})
                else:
                    continue
            elif elem.to_add:
                values = elem.extra_premium[0]._save_values
                values.pop('option', None)
                ex_endorsement = ExtraPremiumEndorsement(action='add',
                    values=values)
                ex_endorsement.values['manual_start_date'] = \
                    self.effective_date
            else:
                continue
            if not (elem.option_endorsement or elem.option.id in new_options):
                option_endorsement = OptionEndorsement(action='update',
                    option=elem.option.id, extra_premiums=[])
                new_options[elem.option.id] = option_endorsement
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
                    new_options[elem.option.id])
            if option_endorsement.id:
                ex_endorsement.covered_option_endorsement = \
                    option_endorsement.id
                to_create.append(ex_endorsement)
            else:
                option_endorsement.extra_premiums = list(
                    option_endorsement.extra_premiums) + [ex_endorsement]
        if to_create:
            # Purge existing endorsements
            option_endorsements = list(set(x.covered_option_endorsement
                    for x in to_create))
            ExtraPremiumEndorsement.delete(ExtraPremiumEndorsement.search([
                        ('covered_option_endorsement', 'in',
                            option_endorsements)]))
            ExtraPremiumEndorsement.create([x._save_values for x in to_create])
        if new_options:
            OptionEndorsement.create([x._save_values
                    for x in new_options.values()
                    if getattr(x, 'covered_element_endorsement', None)])
        if new_covered_elements:
            CoveredElementEndorsement.create([x._save_values
                    for x in new_covered_elements.values()
                    if getattr(x, 'contract_endorsement', None)])
        for endorsement in all_endorsements.itervalues():
            endorsement.clean_up()
        ContractEndorsement.save(all_endorsements.values())


class ManageOptions:
    __name__ = 'contract.manage_options'

    def calculate_possible_parents(self):
        result = super(ManageOptions, self).calculate_possible_parents()
        parents = []
        for parent in result:
            parents.append(parent)
            if isinstance(parent, Pool().get('endorsement.contract')):
                old_covered_elements = list(parent.contract.covered_elements)
                for covered_endorsement in parent.covered_elements:
                    if covered_endorsement.covered_element:
                        old_covered_elements.remove(
                            covered_endorsement.covered_element)
                    if covered_endorsement.action == 'remove':
                        continue
                    parents.append(covered_endorsement)
                parents += old_covered_elements
        return parents

    def update_contract(self):
        pool = Pool()
        if isinstance(self._parent, pool.get(
                    'endorsement.contract.covered_element')):
            self.contract = self._parent.contract_endorsement.contract
        elif isinstance(self._parent, pool.get('contract.covered_element')):
            self.contract = self._parent.contract
        else:
            super(ManageOptions, self).update_contract()

    def get_options_from_parent(self, parent):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        if isinstance(parent, pool.get(
                    'endorsement.contract.covered_element')):
            if parent.action == 'update':
                # Force reinitialization in case we are going backward
                covered_element = CoveredElement(parent.covered_element.id)
                utils.apply_dict(covered_element, parent.apply_values()[2])
            else:
                covered_element = CoveredElement()
                utils.apply_dict(covered_element, parent.apply_values()[1][0])
            options = self.covered_element_options_per_coverage(
                covered_element)
            return options
        elif isinstance(parent, CoveredElement):
            return self.covered_element_options_per_coverage(parent)
        else:
            return super(ManageOptions, self).get_options_from_parent(parent)

    def covered_element_options_per_coverage(self, covered_element):
        per_coverage = defaultdict(list)
        for option in covered_element.options:
            per_coverage[option.coverage].append(option)
        return per_coverage

    def get_parent_name(self, parent):
        if isinstance(parent, Pool().get(
                    'endorsement.contract.covered_element')):
            return parent.party.rec_name if parent.party else parent.name
        return super(ManageOptions, self).get_parent_name(parent)

    @classmethod
    def get_all_possible_coverages(cls, parent):
        pool = Pool()
        if isinstance(parent, pool.get(
                    'endorsement.contract.covered_element')):
            if parent.action == 'update':
                covered_element = parent.covered_element
                utils.apply_dict(covered_element, parent.apply_values()[2])
            else:
                covered_element = pool.get('contract.covered_element')()
                utils.apply_dict(covered_element, parent.apply_values()[1][0])
            contract = parent.contract_endorsement.contract
        elif isinstance(parent, pool.get('contract.covered_element')):
            contract, covered_element = parent.contract, parent
        elif isinstance(parent, pool.get('endorsement.contract')):
            # Remove item_desc related coverages
            return {x for x in
                super(ManageOptions, cls).get_all_possible_coverages(parent)
                if not x.item_desc}
        else:
            raise NotImplementedError
        return {x for x in contract.product.coverages
            if x.item_desc and x.item_desc == covered_element.item_desc}

    def get_parent_endorsed(self, parent, contract_endorsements):
        pool = Pool()
        if isinstance(parent, pool.get('contract.covered_element')):
            contract = contract_endorsements[parent.contract.id]
            contract.covered_elements = list(contract.covered_elements)
            return [x for x in contract.covered_elements if x == parent][0]
        elif isinstance(parent, pool.get(
                    'endorsement.contract.covered_element')):
            contract = contract_endorsements[
                parent.contract_endorsement.contract.id]
            contract.covered_elements = list(contract.covered_elements)
            return [x for x in contract.covered_elements
                if parent.endorsement_matches_record(x)][0]
        else:
            return super(ManageOptions, self).get_parent_endorsed(parent,
                contract_endorsements)

    def get_default_extra_data(self, coverage):
        pool = Pool()
        base_extra_data = super(ManageOptions, self).get_default_extra_data(
            coverage)
        parent = self._parent
        if isinstance(parent, (pool.get('contract.covered_element'),
                    pool.get('endorsement.contract.covered_element'))):
            item_desc = parent.item_desc
        else:
            return base_extra_data
        return self.contract.product.get_extra_data_def('option',
            base_extra_data, self.effective_date, coverage=coverage,
            item_desc=item_desc)


class OptionDisplayer:
    __name__ = 'contract.manage_options.option_displayer'

    @classmethod
    def _option_fields_to_extract(cls):
        to_extract = super(OptionDisplayer, cls)._option_fields_to_extract()
        # No need to extract extra_data, they will be overriden anyway
        to_extract['contract.option'] += ['extra_premiums']
        to_extract['contract.option.extra_premium'] = ['calculation_kind',
            'manual_start_date', 'manual_end_date', 'duration',
            'duration_unit', 'flat_amount', 'motive', 'option', 'rate']
        return to_extract


class OptionSelector(model.CoopView):
    'Option Selector'

    __name__ = 'endorsement.option.selector'

    option_id = fields.Integer('Option Id')
    option_endorsement_id = fields.Integer('Endorsement Id')
    option_rec_name = fields.Char('Option', readonly=True)
    covered_element_id = fields.Integer('Covered Element Id')
    covered_element_endorsement_id = fields.Integer('Endorsement Id')
    covered_element_rec_name = fields.Char('Covered Element', readonly=True)
    selected = fields.Boolean('Selected')

    @classmethod
    def new_selector(cls, option):
        selector = {}
        if option.__name__ == 'contract.option':
            selector['option_id'] = option.id
        else:
            selector['option_endorsement_id'] = option.id
        selector['option_rec_name'] = option.rec_name
        return selector


class CoveredElementSelector(model.CoopView):
    'Covered Element Selector'

    __name__ = 'endorsement.covered_element.selector'

    covered_element_id = fields.Integer('Covered Element Id')
    covered_element_endorsement_id = fields.Integer('Endorsement Id')
    covered_element_rec_name = fields.Char('Covered Element', readonly=True)
    selected = fields.Boolean('Selected')

    @classmethod
    def new_selector(cls, covered_element):
        selector = {}
        if covered_element.__name__ == 'contract.covered_element':
            selector['covered_element_id'] = covered_element.id
        else:
            selector['covered_element_endorsement_id'] = covered_element.id
        selector['covered_element_rec_name'] = covered_element.rec_name
        return selector


class NewExtraPremium(model.CoopView):
    'New Extra Premium'

    __name__ = 'endorsement.contract.new_extra_premium'

    new_extra_premium = fields.One2Many('contract.option.extra_premium', None,
        'New Extra Premium')
    options = fields.One2Many('endorsement.option.selector', None, 'Options')
    option_selected = fields.Boolean('Option Selected', states={
            'invisible': True})
    covered_elements = fields.One2Many('endorsement.covered_element.selector',
        None, 'Covered Elements')

    @classmethod
    def view_attributes(cls):
        return super(NewExtraPremium, cls).view_attributes() + [
            ('/form/group[@id="one_covered"]', 'states',
                {'invisible': Len(Eval('covered_elements', [])) != 1}),
            ('/form/group[@id="multiple_covered"]', 'states',
                {'invisible': Len(Eval('covered_elements', [])) == 1}),
        ]

    @fields.depends('covered_elements', 'option_selected', 'options')
    def on_change_covered_elements(self):
        for covered_element in self.covered_elements:
            for option in self.options:
                if (option.covered_element_id ==
                        covered_element.covered_element_id) and (
                        option.covered_element_endorsement_id ==
                        covered_element.covered_element_endorsement_id):
                    option.selected = covered_element.selected
        self.options = self.options
        self.option_selected = any([x.selected for x in self.options])

    @fields.depends('covered_elements', 'option_selected', 'options')
    def on_change_options(self):
        for covered_element in self.covered_elements:
            covered_element.selected = False
        self.covered_elements = self.covered_elements
        self.option_selected = any((x.selected for x in self.options))

    @classmethod
    def _extra_premium_fields_to_extract(cls):
        return ['calculation_kind', 'capital_per_mil_rate', 'currency',
            'currency_digits', 'currency_symbol', 'duration', 'duration_unit',
            'end_date', 'flat_amount', 'is_discount', 'is_loan', 'max_rate',
            'max_value', 'motive', 'option', 'rate', 'start_date',
            'flat_amount_frequency']

    def update_endorsement(self, wizard):
        all_endorsements = {x.contract.id: x
            for x in wizard.endorsement.contract_endorsements}
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        OptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        ExtraPremiumEndorsement = pool.get(
            'endorsement.contract.extra_premium')
        CoveredElement = pool.get('contract.covered_element')
        new_covered_elements, new_options, to_create = {}, {}, []
        new_values = {
            'action': 'add',
            'values': model.dictionarize(self.new_extra_premium[0],
                self._extra_premium_fields_to_extract()),
            }
        new_values['values'].pop('option', None)
        for option_selector in self.options:
            if not option_selector.selected:
                continue
            if (not option_selector.option_endorsement_id and
                    option_selector.option_id not in new_options):
                option_endorsement = OptionEndorsement(action='update',
                    option=option_selector.option_id, extra_premiums=[])
                new_options[option_selector.option_id] = option_endorsement
                if (not option_selector.covered_element_endorsement_id and
                        option_selector.covered_element_id not in
                        new_covered_elements):
                    covered_element = CoveredElement(
                        option_selector.covered_element_id)
                    ce_endorsement = CoveredElementEndorsement(action='update',
                        options=[option_endorsement],
                        covered_element=covered_element.id,
                        contract_endorsement=all_endorsements[
                            covered_element.contract.id].id)
                    new_covered_elements[covered_element.id] = ce_endorsement
                elif option_selector.covered_element_endorsement_id:
                    option_endorsement.covered_element_endorsement = \
                        option_selector.covered_element_endorsement_id
                else:
                    covered_endorsement = new_covered_elements[
                        option_selector.covered_element_id]
                    covered_endorsement.options = list(
                        covered_endorsement.options) + [option_endorsement]

            save_values = new_values.copy()
            if option_selector.option_endorsement_id:
                save_values['covered_option_endorsement'] = \
                    option_selector.option_endorsement_id
                to_create.append(save_values)
            else:
                new_option = new_options[option_selector.option_id]
                new_option.extra_premiums = list(new_option.extra_premiums) + [
                    ExtraPremiumEndorsement(**save_values)]
        if to_create:
            ExtraPremiumEndorsement.create(to_create)
        if new_options:
            OptionEndorsement.create([x._save_values
                    for x in new_options.itervalues()
                    if getattr(x, 'covered_element_endorsement', None)])
        if new_covered_elements:
            CoveredElementEndorsement.create([x._save_values
                    for x in new_covered_elements.itervalues()
                    if getattr(x, 'contract_endorsement', None)])
        for endorsement in all_endorsements.itervalues():
            endorsement.clean_up()
        ContractEndorsement.save(all_endorsements.values())


class ManageExclusions(EndorsementWizardStepMixin):
    'Manage Exclusions'

    __name__ = 'contract.manage_exclusions'

    contract = fields.Many2One('endorsement.contract', 'Contract',
        domain=[('id', 'in', Eval('possible_contracts', []))],
        states={'invisible': Len(Eval('possible_contracts', [])) <= 1},
        depends=['possible_contracts'])
    possible_contracts = fields.Many2Many('endorsement.contract', None, None,
        'Possible Contracts')
    current_options = fields.One2Many('contract.manage_exclusions.option',
        None, 'Options')
    all_options = fields.One2Many('contract.manage_exclusions.option',
        None, 'Options')

    @classmethod
    def view_attributes(cls):
        return super(ManageExclusions, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ]

    @classmethod
    def state_view_name(cls):
        return 'endorsement_insurance.endorsement_manage_exclusions_view_form'

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
        defaults = super(ManageExclusions, self).step_default()
        possible_contracts = self.wizard.endorsement.contract_endorsements
        defaults['possible_contracts'] = [x.id for x in possible_contracts]
        per_contract = {x: self.get_updated_options_from_contract(x)
            for x in possible_contracts}

        all_options = []
        for contract, options in per_contract.iteritems():
            all_options += self.generate_displayers(contract, options)
        defaults['all_options'] = [model.serialize_this(x)
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
        Displayer = pool.get('contract.manage_exclusions.option')
        Exclusion = pool.get('contract.option-exclusion.kind')
        per_key = {Displayer.get_parent_key(x): x
            for covered in contract_endorsement.contract.covered_elements
            for x in covered.options}
        for option in options:
            patched_option = per_key[option.parent]
            if option.option_id:
                old_exclusions = {x.exclusion: x
                    for x in Option(option.option_id).exclusion_list}
            else:
                old_exclusions = {}
            exclusions = []
            for exclusion in option.exclusions:
                if exclusion.action == 'removed':
                    continue
                if exclusion.action == 'added':
                    exclusions.append(Exclusion(exclusion=exclusion.exclusion))
                    continue
                # action == 'nothing' => already existed
                exclusions.append(old_exclusions[exclusion.exclusion])
            patched_option.exclusion_list = exclusions

    def get_updated_options_from_contract(self, contract_endorsement):
        contract = contract_endorsement.contract
        utils.apply_dict(contract, contract_endorsement.apply_values())
        return self.get_contract_options(contract)

    def get_contract_options(self, contract):
        return [x for covered in contract.covered_elements
            for x in covered.options]

    def generate_displayers(self, contract_endorsement, options):
        pool = Pool()
        Option = pool.get('contract.manage_exclusions.option')
        all_options = []
        for option in options:
            displayer = Option.new_displayer(option)
            displayer.contract = contract_endorsement.id
            all_options.append(displayer)
        return all_options


class ManageExclusionsOptionDisplayer(model.CoopView):
    'Manage Exclusions Option Displayer'

    __name__ = 'contract.manage_exclusions.option'

    parent_name = fields.Char('Parent', readonly=True)
    parent = fields.Char('Parent', readonly=True)
    contract = fields.Integer('Contract', readonly=True)
    option_id = fields.Integer('Option', readonly=True)
    display_name = fields.Char('Option', readonly=True)
    exclusions = fields.One2Many('contract.manage_exclusions.exclusion', None,
        'Exclusions')

    @classmethod
    def new_displayer(cls, option):
        pool = Pool()
        Option = pool.get('contract.option')
        Exclusion = pool.get('contract.manage_exclusions.exclusion')
        displayer = cls()
        displayer.parent_name = (option.covered_element
            or option.contract).rec_name
        displayer.parent = cls.get_parent_key(option)
        displayer.option_id = getattr(option, 'id', None)
        displayer.display_name = option.get_rec_name(None)

        new_exclusions = {x.exclusion for x in getattr(option,
                'exclusion_list', [])}
        if displayer.option_id:
            current_exclusions = {x.exclusion
                for x in Option(displayer.option_id).exclusion_list}
        else:
            current_exclusions = set([])

        exclusions = [Exclusion(exclusion=x, action='nothing')
            for x in current_exclusions & new_exclusions]
        exclusions += [Exclusion(exclusion=x, action='added')
            for x in new_exclusions - current_exclusions]
        exclusions += [Exclusion(exclusion=x, action='removed')
            for x in current_exclusions - new_exclusions]
        exclusions.sort(key=lambda x: x.exclusion.rec_name)
        displayer.exclusions = exclusions
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


class ManageExclusionsDisplayer(model.CoopView):
    'Manage Exclusions Displayer'

    __name__ = 'contract.manage_exclusions.exclusion'

    exclusion = fields.Many2One('offered.exclusion', 'Exclusion Kind',
        required=True)
    action = fields.Selection([('nothing', 'Nothing'),
            ('added', 'Added'), ('removed', 'Removed')], 'Action')

    @classmethod
    def default_action(cls):
        return 'added'


class VoidContract:
    __name__ = 'endorsement.contract.void'

    def step_update(self):
        pool = Pool()
        CovOptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        Contract = pool.get('contract')
        contract_id, endorsement = self._get_contracts().items()[0]
        contract = Contract(contract_id)
        cov_elem_endorsements = []
        for cov in contract.covered_elements:
            cov_elem_endorsements.append(CoveredElementEndorsement(
                    contract_endorsement=endorsement,
                    action='update', relation=cov.id,
                    options=[CovOptionEndorsement(
                            action='update',
                            relation=option.id,
                            definition=self.endorsement_definition,
                            values={'status': 'void',
                                'sub_status': self.void_reason.id})
                        for option in cov.options]))
        endorsement.covered_elements = cov_elem_endorsements
        super(VoidContract, self).step_update()


class StartEndorsement:
    __name__ = 'endorsement.start'

    new_covered_element = StateView('contract.covered_element.new',
        'endorsement_insurance.new_covered_element_view_form', [
            Button('Previous', 'new_covered_element_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'new_covered_element_suspend', 'tryton-save'),
            Button('Next', 'new_covered_element_next', 'tryton-go-next')])
    new_covered_element_previous = StateTransition()
    new_covered_element_next = StateTransition()
    new_covered_element_suspend = StateTransition()
    new_option_covered_element = StateView(
        'contract.covered_element.add_option',
        'endorsement_insurance.add_option_to_covered_element_view_form', [
            Button('Previous', 'new_option_covered_element_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'new_option_covered_element_next',
                'tryton-go-next')])
    new_option_covered_element_previous = StateTransition()
    new_option_covered_element_next = StateTransition()
    manage_extra_premium = StateView(
        'endorsement.contract.manage_extra_premium',
        'endorsement_insurance.manage_extra_premium_view_form', [
            Button('Previous', 'manage_extra_premium_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('New Extra Premium', 'start_new_extra_premium',
                'tryton-new'),
            Button('Next', 'manage_extra_premium_next',
                'tryton-go-next')])
    manage_extra_premium_previous = StateTransition()
    start_new_extra_premium = StateTransition()
    new_extra_premium = StateView('endorsement.contract.new_extra_premium',
        'endorsement_insurance.new_extra_premium_view_form', [
            Button('Cancel', 'manage_extra_premium', 'tryton-go-previous'),
            Button('Continue', 'add_extra_premium', 'tryton-go-next',
                default=True, states={'readonly': ~Eval('option_selected')})])
    add_extra_premium = StateTransition()
    manage_extra_premium_next = StateTransition()
    remove_option = StateView('contract.covered_element.option.remove',
        'endorsement_insurance.remove_option_view_form', [
            Button('Previous', 'remove_option_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'remove_option_suspend', 'tryton-save'),
            Button('Next', 'remove_option_next', 'tryton-go-next')])
    remove_option_previous = StateTransition()
    remove_option_next = StateTransition()
    remove_option_suspend = StateTransition()

    def set_main_object(self, endorsement):
        super(StartEndorsement, self).set_main_object(endorsement)
        endorsement.covered_elements = []

    def update_default_covered_element_from_endorsement(self, endorsements,
            default_values):
        for endorsement in endorsements:
            default_covered_elements = default_values['covered_elements']
            for i, covered_element in enumerate(endorsement.covered_elements):
                if covered_element.action == 'add':
                    default_covered_elements[i].update(covered_element.values)

    def default_new_covered_element(self, name):
        endorsement_part = self.get_endorsement_part_for_state(
            'new_covered_element')
        contract = self.get_endorsed_object(endorsement_part)
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'product': self.select_endorsement.product.id,
            'start_date': endorsement_date,
            'contract': contract.id,
            'possible_item_desc': [x.id for x in contract.possible_item_desc],
            'extra_datas': [x.id for x in contract.extra_datas],
            }
        num_covered_elements = 1
        if (self.endorsement.contract_endorsements and
                self.endorsement.contract_endorsements[0].covered_elements):
            num_covered_elements = len(
                self.endorsement.contract_endorsements[0].covered_elements)
        result['covered_elements'] = [{
                'item_desc': (result['possible_item_desc'] or [None])[0],
                'main_contract': contract.id,
                'contract': contract.id,
                'product': result['product'],
                } for _ in xrange(num_covered_elements)]
        for covered_elem in result['covered_elements']:
            new_covered_element = Pool().get('contract.covered_element')(
                **covered_elem)
            new_covered_element.on_change_item_desc()
            covered_elem.update(
                new_covered_element._default_values)
        endorsements = self.get_endorsements_for_state('new_covered_element')
        if endorsements:
            self.update_default_covered_element_from_endorsement(endorsements,
                result)
        return result

    def transition_new_covered_element_suspend(self):
        self.end_current_part('new_covered_element')
        return 'end'

    def transition_new_covered_element_next(self):
        self.end_current_part('new_covered_element')
        return self.get_next_state('new_covered_element')

    def transition_new_covered_element_previous(self):
        self.end_current_part('new_covered_element')
        return self.get_state_before('new_covered_element')

    def default_new_option_covered_element(self, name):
        endorsement_part = self.get_endorsement_part_for_state(
            'new_option_covered_element')
        contract = self.get_endorsed_object(endorsement_part)
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            'possible_covered_elements': [
                x.id for x in contract.covered_elements],
            }
        if len(result['possible_covered_elements']) == 1:
            result['covered_element'] = result['possible_covered_elements'][0]
        endorsement = self.get_endorsements_for_state(
            'new_option_covered_element')
        if endorsement:
            NewOptionState = Pool().get('contract.covered_element.add_option')
            result.update(NewOptionState.update_default_values(self,
                    endorsement[0], result))
        return result

    def transition_new_option_covered_element_next(self):
        self.end_current_part('new_option_covered_element')
        return self.get_next_state('new_option_covered_element')

    def transition_new_option_covered_element_previous(self):
        self.end_current_part('new_option_covered_element')
        return self.get_state_before('new_option_covered_element')

    def default_manage_extra_premium(self, name):
        ContractEndorsement = Pool().get('endorsement.contract')
        endorsement_part = self.get_endorsement_part_for_state(
            'manage_extra_premium')
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            }
        endorsements = self.get_endorsements_for_state('manage_extra_premium')
        if not endorsements:
            if self.select_endorsement.contract:
                endorsements = [ContractEndorsement(definition=self.definition,
                        endorsement=self.endorsement,
                        contract=self.select_endorsement.contract)]
            else:
                return result
        ManageExtraPremium = Pool().get(
            'endorsement.contract.manage_extra_premium')
        result.update(ManageExtraPremium.update_default_values(self,
                endorsements[0], result))
        return result

    def transition_start_new_extra_premium(self):
        self.end_current_part('manage_extra_premium')
        return 'new_extra_premium'

    def default_new_extra_premium(self, name):
        pool = Pool()
        CoveredElementSelector = pool.get(
            'endorsement.covered_element.selector')
        OptionSelector = pool.get('endorsement.option.selector')
        endorsements = list(self.endorsement.contract_endorsements)
        contract = endorsements[0].contract
        default_values = {
            'new_extra_premium': [{
                    'start_date': self.select_endorsement.effective_date,
                    'manual_start_date':
                    self.select_endorsement.effective_date,
                    'duration_unit': pool.get(
                        'contract.option.extra_premium').default_duration_unit(
                        ),
                    # Set fake option to bypass required in view
                    'option': (contract.options +
                        contract.covered_element_options)[0].id,
                    'currency': contract.currency.id,
                    'currency_symbol': contract.currency_symbol,
                    }],
            'covered_elements': [],
            'options': [],
            }

        for endorsement in endorsements:
            updated_struct = endorsement.updated_struct
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                default_values['covered_elements'].append(
                    CoveredElementSelector.new_selector(covered_element))
                for option, o_values in values['options'].iteritems():
                    default_values['options'].append(
                        OptionSelector.new_selector(option))
                    default_values['options'][-1].update(
                        default_values['covered_elements'][-1])
        return default_values

    def transition_add_extra_premium(self):
        self.new_extra_premium.update_endorsement(self)
        return 'manage_extra_premium'

    def transition_manage_extra_premium_previous(self):
        self.end_current_part('manage_extra_premium')
        return self.get_state_before('manage_extra_premium')

    def transition_manage_extra_premium_next(self):
        self.end_current_part('manage_extra_premium')
        return self.get_next_state('manage_extra_premium')

    def default_remove_option(self, name):
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        endorsement_part = self.get_endorsement_part_for_state(
            'remove_option')
        result = {
            'endorsement_part': endorsement_part.id,
            'endorsement_definition': self.definition.id,
            }
        endorsements = self.get_endorsements_for_state('remove_option')
        if not endorsements:
            if self.select_endorsement.contract:
                endorsements = [ContractEndorsement(definition=self.definition,
                        endorsement=self.endorsement,
                        contract=self.select_endorsement.contract)]
            else:
                return result
        result['options'] = []
        RemoveOption = pool.get(
            'contract.covered_element.option.remove')
        result.update(RemoveOption.update_default_values(self,
                endorsements[0], result))
        return result

    def transition_remove_option_suspend(self):
        self.end_current_part('remove_option')
        return 'end'

    def transition_remove_option_next(self):
        self.end_current_part('remove_option')
        return self.get_next_state('remove_option')

    def transition_remove_option_previous(self):
        self.end_current_part('remove_option')
        return self.get_state_before('remove_option')


add_endorsement_step(StartEndorsement, ModifyCoveredElement,
    'modify_covered_element')

add_endorsement_step(StartEndorsement, ManageExclusions, 'manage_exclusions')

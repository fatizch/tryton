# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Null
from sql.aggregate import Count

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, model


__all__ = [
    'IndemnificationDefinition',
    'CreateIndemnification',
    'TransferServices',
    'TransferServicesContracts',
    'TransferServicesBenefits',
    'TransferServicesBenefitLine',
    ]


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    @fields.depends('beneficiary')
    def on_change_service(self):
        super(IndemnificationDefinition, self).on_change_service()

    @fields.depends('beneficiary', 'possible_products', 'product', 'service')
    def on_change_beneficiary(self):
        super(IndemnificationDefinition, self).on_change_beneficiary()
        self.update_product()

    def get_possible_products(self, name):
        if not self.beneficiary or self.beneficiary.is_person:
            return super(IndemnificationDefinition,
                self).get_possible_products(name)
        if self.service:
            return [x.id for x in self.service.benefit.company_products]
        return []


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    @classmethod
    def __setup__(cls):
        super(CreateIndemnification, cls).__setup__()
        cls._error_messages.update({
                'bad_start_date': 'The contract was terminated on the '
                '%(contract_end)s, a new indemnification cannot start on '
                '%(indemn_start)s.',
                'truncated_end_date': 'The contract was terminated on the '
                '%(contract_end)s, so the requested indemnification end ('
                '%(indemn_end)s) will automatically be updated',
                'lock_end_date': 'The contract was terminated on the '
                '%(contract_end)s, there will not be any revaluation '
                'after this date',
                })

    def default_definition(self, name):
        Party = Pool().get('party.party')
        defaults = super(CreateIndemnification, self).default_definition(name)
        if not defaults.get('service', None) or not defaults.get('start_date',
                None):
            return defaults
        service = Pool().get('claim.service')(defaults['service'])
        if service.contract and service.contract.end_date:
            contract_end = service.contract.end_date
            if contract_end < defaults['start_date']:
                if (service.contract.post_termination_claim_behaviour ==
                        'stop_indemnifications'):
                    self.raise_user_error('bad_start_date', {
                            'indemn_start': defaults['start_date'],
                            'contract_end': contract_end})
        # beneficiary become the employee once he leave the company
        if (service.contract.is_group and not service.manual_beneficiaries and
                not Party(defaults['beneficiary']).is_person):
            if (service.theoretical_covered_element and
                    service.theoretical_covered_element.contract_exit_date and
                    defaults['start_date'] >=
                    service.theoretical_covered_element.contract_exit_date):
                defaults['beneficiary'] = service.loss.covered_person.id
                defaults['product'] = None
        return defaults

    def check_input(self):
        res = super(CreateIndemnification, self).check_input()
        input_start_date = self.definition.start_date
        input_end_date = self.definition.end_date
        service = self.definition.service
        if (input_start_date and service.contract and
                service.contract.end_date):
            contract_end = service.contract.end_date
            behaviour = service.contract.post_termination_claim_behaviour
            if contract_end < input_start_date:
                if behaviour == 'stop_indemnifications':
                    self.raise_user_error('bad_start_date', {
                            'indemn_start': input_start_date,
                            'contract_end': contract_end})
            if contract_end < input_end_date:
                if behaviour == 'stop_indemnifications':
                    self.raise_user_warning(
                        'truncated_end_date_%i' % service.id,
                        'truncated_end_date', {
                            'indemn_end': input_end_date,
                            'contract_end': contract_end})
                    input_end_date = contract_end
                elif behaviour == 'lock_indemnifications':
                    self.raise_user_warning(
                        'lock_end_date_%i' % service.id,
                        'lock_end_date', {
                            'indemn_end': input_end_date,
                            'contract_end': contract_end})
        return res


class TransferServices(Wizard):
    'Transfer Services'

    __name__ = 'claim.transfer_services'

    start_state = 'select_contracts'
    select_contracts = StateView('claim.transfer_services.contracts',
        'claim_indemnification_group.transfer_services_contracts_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Match Benefits', 'benefits', 'tryton-go-next',
                default=True)])
    benefits = StateView('claim.transfer_services.benefits',
        'claim_indemnification_group.transfer_services_benefits_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Transfer', 'transfer', 'tryton-go-next',
                default=True)])
    transfer = StateTransition()

    def default_select_contracts(self, name):
        if Transaction().context.get('active_model', '') != 'contract':
            return {}
        return {
            'source_contract': Transaction().context.get('active_id', None),
            }

    def default_benefits(self, name):
        TransferServicesContracts = Pool().get(
             'claim.transfer_services.contracts')
        source = self.select_contracts.source_contract
        target = self.select_contracts.target_contract

        possible_covered = [x.id for x in target.covered_elements]

        lines = []
        source_data = TransferServicesContracts.benefit_data(source,
            source.end_date)
        for benefit, option_list in source_data.iteritems():
            for option, number in option_list:
                lines.append({
                        'number': number,
                        'source_benefit': benefit.id,
                        'source_covered': option.covered_element.id,
                        'source_option': option.covered_element.id,
                        })
        return {
            'possible_covered': possible_covered,
            'lines': lines,
            }

    def transition_transfer(self):
        Service = Pool().get('claim.service')
        Service.transfer_services([(x.source_benefit, x.source_option,
                    x.target_benefit, x.target_option)
                for x in self.benefits.lines],
            self.select_contracts.source_contract.end_date)
        return 'end'


class TransferServicesContracts(model.CoogView):
    'Transfer Services Contracts'

    __name__ = 'claim.transfer_services.contracts'

    source_contract = fields.Many2One('contract', 'Source Contract', domain=[
            ('product.is_group', '=', True), ('status', '=', 'terminated')],
        required=True)
    target_contract = fields.Many2One('contract', 'Target Contract', domain=[
            ('product.is_group', '=', True), ('status', '=', 'active')],
        required=True)
    source_product = fields.Many2One('offered.product', 'Source Product',
        readonly=True)
    target_product = fields.Many2One('offered.product', 'Target Product',
        readonly=True)
    source_benefits = fields.Text('Source Benefits', readonly=True)
    target_benefits = fields.Text('Target Benefits', readonly=True)

    @classmethod
    def __setup__(cls):
        super(TransferServicesContracts, cls).__setup__()
        cls._error_messages.update({
                'benefit_displayer': '%s (%i claims)',
                })

    @classmethod
    def benefit_data(cls, contract, at_date):
        pool = Pool()
        service = pool.get('claim.service').__table__()
        loss = pool.get('claim.loss').__table__()
        Benefit = pool.get('benefit')
        Option = pool.get('contract.option')
        options = list(contract.options) + list(
            contract.covered_element_options)

        cursor = Transaction().connection.cursor()

        cursor.execute(*service.join(loss, condition=loss.id == service.loss
                ).select(service.benefit, service.option, Count(service.id),
                where=service.option.in_([x.id for x in options])
                & ((loss.end_date != Null)
                    | (loss.end_date >= at_date)),
                group_by=[service.benefit, service.option],
                order_by=service.benefit))

        output = cursor.fetchall()
        benefits = Benefit.browse([x[0] for x in output])
        options = Option.browse([x[1] for x in output])
        res = defaultdict(list)
        for benefit, option, (_, _, number) in zip(benefits, options, output):
            res[benefit].append((option, number))
        return res

    @fields.depends('source_contract', 'source_benefits', 'source_product',
        'target_contract')
    def on_change_source_contract(self):
        if not self.source_contract or not self.target_contract:
            self.source_benefits = ''
            self.source_product = None
            return
        self.source_product = self.source_contract.product
        benefit_data = self.benefit_data(self.source_contract,
            self.target_contract.end_date)
        self.source_benefits = '\n'.join([self.raise_user_error(
                    'benefit_displayer', (b.rec_name, len(o)),
                    raise_exception=False) for b, o in benefit_data.items()])

    @fields.depends('target_contract', 'target_benefits', 'target_product')
    def on_change_target_contract(self):
        if not self.target_contract:
            self.target_benefits = ''
            self.target_product = None
            return
        self.target_product = self.target_contract.product
        benefit_data = self.benefit_data(self.target_contract,
            self.target_contract.end_date)
        self.target_benefits = '\n'.join([self.raise_user_error(
                    'benefit_displayer', (b.rec_name, len(o)),
                    raise_exception=False) for b, o in benefit_data.items()])


class TransferServicesBenefits(model.CoogView):
    'Transfer Services Benefits'

    __name__ = 'claim.transfer_services.benefits'

    lines = fields.One2Many('claim.transfer_services.benefit_line', None,
        'Lines', domain=[('target_covered', 'in', Eval('possible_covered'))],
        depends=['possible_covered'])
    possible_covered = fields.Many2Many('contract.covered_element', None, None,
        'Possible Covered Elements', readonly=True)

    @fields.depends('lines')
    def on_change_lines(self):
        self.lines = [x for x in self.lines if x.source_benefit]


class TransferServicesBenefitLine(model.CoogView):
    'Transfer Services Benefit Line'

    __name__ = 'claim.transfer_services.benefit_line'

    number = fields.Integer('Number', readonly=True)
    source_covered = fields.Many2One('contract.covered_element',
        'Source Covered', readonly=True)
    source_option = fields.Many2One('contract.option', 'Source Option',
        readonly=True)
    source_benefit = fields.Many2One('benefit', 'Source Benefit',
        readonly=True)
    target_covered = fields.Many2One('contract.covered_element',
        'Target Covered', required=True)
    target_option = fields.Many2One('contract.option', 'Target Option',
        domain=[If(~Eval('target_covered'), [], [
                    ('covered_element', '=', Eval('target_covered'))])],
        states={'invisible': ~Eval('target_covered')},
        depends=['target_covered'], required=True)
    target_benefit = fields.Many2One('benefit', 'Target Benefit', domain=[
            ('id', 'in', Eval('possible_benefits'))], states={
            'readonly': ~Eval('target_option')}, required=True,
        depends=['target_option', 'possible_benefits'])
    possible_benefits = fields.Many2Many('benefit', None, None,
        'Possible Benefits', readonly=True)

    @fields.depends('target_covered', 'target_option')
    def on_change_target_covered(self):
        if not self.target_covered:
            self.target_option = None
        elif len(self.target_covered.options) == 1:
            self.target_option = self.target_covered.options[0]
            self.possible_benefits = list(self.target_option.coverage.benefits)
        else:
            self.target_option = None

    @fields.depends('target_covered', 'target_option')
    def on_change_target_option(self):
        if self.target_option:
            self.target_covered = self.target_option.covered_element
            self.possible_benefits = list(self.target_option.coverage.benefits)
        else:
            self.possible_benefits = []

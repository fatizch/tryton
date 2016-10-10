# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields, coog_date

__all__ = [
    'TransferCoveredElements',
    'TransferCoveredElementsContracts',
    'TransferCoveredElementsItemDescs',
    'TransferCoveredElementsItemDescLine',
    ]


class TransferCoveredElements(Wizard):
    'Transfer Covered Elements'

    __name__ = 'contract.transfer_covered_elements'

    start_state = 'select_contracts'
    select_contracts = StateView('contract.transfer_covered_elements.contracts',
        'contract_group.transfer_covered_elements_contracts_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Check Item Descs', 'item_descs', 'tryton-go-next',
                default=True)])
    item_descs = StateView('contract.transfer_covered_elements.item_descs',
        'contract_group.transfer_covered_elements_item_descs_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Transfer', 'transfer', 'tryton-go-next', default=True)])
    transfer = StateTransition()

    @classmethod
    def __setup__(cls):
        super(TransferCoveredElements, cls).__setup__()
        cls._error_messages.update({
                'non_covered_period': 'There is a non covered period, source '
                'contract ends on the %(source_end)s when target starts on '
                '%(target_start)s.',
                })

    def default_select_contracts(self, name):
        if Transaction().context.get('active_model', '') != 'contract':
            return {}
        return {
            'source_contract': Transaction().context.get('active_id', None),
            }

    def check_input(self):
        source = self.select_contracts.source_contract
        target = self.select_contracts.target_contract
        if coog_date.add_day(source.end_date, 1) != target.start_date:
            self.raise_user_warning('non_covered_period_%i' % source.id,
                'non_covered_period', {
                    'source_end': str(source.end_date),
                    'target_start': str(target.start_date)})

    def default_item_descs(self, name):
        self.check_input()
        source = self.select_contracts.source_contract
        target = self.select_contracts.target_contract
        lines = []
        possible_targets = set([x.id for x in target.covered_elements])
        per_item_desc = defaultdict(list)
        for covered in target.covered_elements:
            possible_targets.add(covered.id)
            per_item_desc[covered.item_desc.id].append(covered)
        for covered_element in source.covered_elements:
            if not covered_element.is_covered_at_date(source.end_date):
                continue
            sub_covered = [x for x in covered_element.sub_covered_elements
                if x.is_valid_at_date(source.end_date)]
            if not sub_covered:
                continue
            lines.append({
                    'source_covered': covered_element.id,
                    'number': len(sub_covered),
                    })
            if len(per_item_desc[covered_element.item_desc.id]) == 1:
                lines[-1]['target_covered'] = per_item_desc[
                    covered_element.item_desc.id][0].id
        if len(lines) == 1 and len(target.covered_elements) == 1:
            lines[0]['target_covered'] = target.covered_elements[0].id
        return {
            'lines': lines,
            'possible_targets': list(possible_targets),
            }

    def transition_transfer(self):
        CoveredElement = Pool().get('contract.covered_element')
        CoveredElement.transfer_sub_covered({
                line.source_covered: line.target_covered
                for line in self.item_descs.lines},
            self.select_contracts.source_contract.end_date)
        return 'end'


class TransferCoveredElementsContracts(model.CoogView):
    'Transfer Covered Elements Contracts'

    __name__ = 'contract.transfer_covered_elements.contracts'

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
    source_item_descs = fields.Text('Source Item Descs', readonly=True)
    target_item_descs = fields.Text('Target Item Descs', readonly=True)

    @classmethod
    def __setup__(cls):
        super(TransferCoveredElementsContracts, cls).__setup__()
        cls._error_messages.update({
                'covered_element_displayer': '%s (%i covered elements)',
                })

    @fields.depends('source_contract', 'source_item_descs', 'source_product')
    def on_change_source_contract(self):
        if not self.source_contract:
            self.source_item_descs = ''
            self.source_product = None
            return
        self.source_product = self.source_contract.product
        descs = []
        for elem in self.source_contract.covered_elements:
            descs.append(self.raise_user_error('covered_element_displayer',
                    (elem.rec_name, len(elem.sub_covered_elements)),
                    raise_exception=False))
        self.source_item_descs = '\n'.join(descs)

    @fields.depends('target_contract', 'target_item_descs', 'target_product')
    def on_change_target_contract(self):
        if not self.target_contract:
            self.target_item_descs = ''
            self.target_product = None
            return
        self.target_product = self.target_contract.product
        descs = []
        for elem in self.target_contract.covered_elements:
            descs.append(self.raise_user_error('covered_element_displayer',
                    (elem.rec_name, len(elem.sub_covered_elements)),
                    raise_exception=False))
        self.target_item_descs = '\n'.join(descs)


class TransferCoveredElementsItemDescs(model.CoogView):
    'Transfer Covered Elements Item Descs'

    __name__ = 'contract.transfer_covered_elements.item_descs'

    lines = fields.One2Many(
        'contract.transfer_covered_elements.item_desc_line', None, 'Lines',
        domain=[('target_covered', 'in', Eval('possible_targets'))],
        depends=['possible_targets'])
    possible_targets = fields.Many2Many('contract.covered_element', None, None,
        'Possible Targets', readonly=True)

    @fields.depends('lines')
    def on_change_lines(self):
        self.lines = [x for x in self.lines if x.source_covered]


class TransferCoveredElementsItemDescLine(model.CoogView):
    'Transfer Covered Elements Item Desc Line'

    __name__ = 'contract.transfer_covered_elements.item_desc_line'

    source_covered = fields.Many2One('contract.covered_element',
        'Source Covered', readonly=True, help='One of the source contract '
        'covered elements with sub covered elements to transfer')
    target_covered = fields.Many2One('contract.covered_element',
        'Target Covered', required=True, help='The covered element of the '
        'target contract to transfer the sub covered elements to')
    number = fields.Integer('Number', readonly=True)

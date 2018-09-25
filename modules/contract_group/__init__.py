# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.functions import CurrentDate

from trytond.pool import Pool

import offered
import contract
import party
import wizard
import rule_engine


def get_organization_hierarchy():
    '''
        Will be used to generate the party.hierarchy union mixin. The final
        structure will look like below, with:
            [R] being the root node
            [N] being "folders" nodes (i.e. singleton nodes that are only here
                for "organizing" the data
            [D] being "data" nodes, with list of elements matching the folder
                node above them

        [R] party.hierarchy
            [N] party.hierarchy.party
                [N] party.hierarchy.contract
                    [D] party.hierarchy.contracts
                        [D] party.hierarchy.contracts.covereds
                        [N] party.hierarchy.contracts.terminated_covered
                            [D] party.hierarchy.contracts.terminated_covereds
                [N] party.hierarchy.contract.terminated
                    [D] party.hierarchy.contracts.terminated
                        [D] party.hierarchy.terminated_contracts.covered
                [D] party.hierarchy.covereds
                [N] party.hierarchy.terminated_covered
                    [D] party.hierarchy.terminated_covereds
            [N] party.hierarchy.subsidiary
                [D] party.hierarchy.subsidiaries
                    [D] party.hierarchy.subsidiary.contracts
                    [D] party.hierarchy.subsidiary.covereds
                    [N] party.hierarchy.subsidiary.terminated
                        [D] party.hierarchy.subsidiary.terminated.contracts
                        [D] party.hierarchy.subsidiary.terminated.covereds
    '''
    subsidiary_terminated_contracts = {
        'node_name': 'party.hierarchy.subsidiary.terminated.contracts',
        'model': 'contract',
        'main_field': 'subscriber',
        'type': 'data',
        'domain': [('status', 'in', ['terminated', 'void'])],
        }
    subsidiary_terminated_covereds = {
        'node_name': 'party.hierarchy.subsidiary.terminated.covereds',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'type': 'data',
        'domain': [('manual_end_date', '<', CurrentDate)],
        'name_func': lambda x: '%s - %s - %s' % (
            x.contract.get_synthesis_rec_name(None),
            x.parent.rec_name, x.rec_name),
        }
    subsidiary_terminated = {
        'node_name': 'party.hierarchy.subsidiary.terminated',
        'model': 'party.party',
        'main_field': 'id',
        'type': 'node',
        'icon': 'contract_red',
        'name': 'Terminated',
        'domain': ['OR', ('contracts.status', 'in', ('void', 'terminated')),
            ('covered_elements', 'where',
                ('manual_end_date', '<', CurrentDate)),
            ],
        'childs': [subsidiary_terminated_contracts,
            subsidiary_terminated_covereds],
        }
    subsidiary_covered = {
        'node_name': 'party.hierarchy.subsidiary.covereds',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'type': 'data',
        'domain': ['OR', ('manual_end_date', '=', None),
            ('manual_end_date', '>=', CurrentDate)],
        'name_func': lambda x: '%s - %s - %s' % (
            x.contract.get_synthesis_rec_name(None),
            x.parent.rec_name, x.rec_name),
        }
    subsidiary_contracts = {
        'node_name': 'party.hierarchy.subsidiary.contracts',
        'model': 'contract',
        'main_field': 'subscriber',
        'type': 'data',
        'domain': [('status', 'not in', ['terminated', 'void'])],
        }
    subsidiaries = {
        'node_name': 'party.hierarchy.subsidiaries',
        'model': 'party.party',
        'main_field': 'id',
        'parent_field': 'parent_company',
        'type': 'data',
        'domain': [('parent_company', '!=', None)],
        'childs': [subsidiary_contracts, subsidiary_covered,
            subsidiary_terminated],
        }
    subsidiary = {
        'node_name': 'party.hierarchy.subsidiary',
        'model': 'party.party',
        'main_field': 'parent_company',
        'type': 'node',
        'icon': 'coopengo-company',
        'name': 'Subsidiaries',
        'childs': [subsidiaries],
        }
    terminated_covereds = {
        'node_name': 'party.hierarchy.terminated_covereds',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'type': 'data',
        'domain': [('manual_end_date', '<', CurrentDate)],
        'name_func': lambda x: '%s - %s - %s' % (
            x.contract.rec_name, x.rec_name, x.parent.rec_name),
        }
    terminated_covered_root = {
        'node_name': 'party.hierarchy.terminated_covered',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'type': 'node',
        'icon': 'contract_red',
        'name': 'Terminated Covereds',
        'domain': [('manual_end_date', '<', CurrentDate)],
        'childs': [terminated_covereds],
        }
    covereds = {
        'node_name': 'party.hierarchy.covereds',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'type': 'data',
        'domain': ['OR', ('manual_end_date', '=', None),
            ('manual_end_date', '>=', CurrentDate)],
        'name_func': lambda x: '%s - %s - %s' % (
            x.contract.rec_name, x.rec_name, x.parent.rec_name),
        }
    terminated_contracts_covereds = {
        'node_name': 'party.hierarchy.terminated_contracts.covered',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'parent_field': 'contract',
        'type': 'data',
        'domain': [('item_desc.kind', '=', 'subsidiary')],
        'name_func': lambda x: '%s - %s' % (x.parent.rec_name, x.rec_name),
        }
    terminated_contracts = {
        'node_name': 'party.hierarchy.contracts.terminated',
        'model': 'contract',
        'main_field': 'subscriber',
        'type': 'data',
        'domain': [('status', 'in', ['void', 'terminated'])],
        'childs': [terminated_contracts_covereds],
        }
    terminated_contract_root = {
        'node_name': 'party.hierarchy.contract.terminated',
        'model': 'contract',
        'main_field': 'subscriber',
        'type': 'node',
        'icon': 'contract_red',
        'name': 'Terminated Contracts',
        'domain': [('status', 'in', ['void', 'terminated'])],
        'childs': [terminated_contracts],
        }
    contracts_terminated_covereds = {
        'node_name': 'party.hierarchy.contracts.terminated_covereds',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'parent_field': 'contract',
        'type': 'data',
        'domain': [('item_desc.kind', '=', 'subsidiary'),
            ('manual_end_date', '<', CurrentDate)],
        'name_func': lambda x: '%s - %s' % (x.rec_name, x.parent.rec_name),
        }
    contracts_terminated_covered_root = {
        'node_name': 'party.hierarchy.contracts.terminated_covered',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'parent_field': 'contract',
        'type': 'node',
        'icon': 'contract_red',
        'name': 'Terminated Covereds',
        'domain': [('item_desc.kind', '=', 'subsidiary'),
            ('manual_end_date', '<', CurrentDate)],
        'childs': [contracts_terminated_covereds],
        }
    contracts_covereds = {
        'node_name': 'party.hierarchy.contracts.covereds',
        'model': 'contract.covered_element',
        'main_field': 'party',
        'parent_field': 'contract',
        'type': 'data',
        'domain': [('item_desc.kind', '=', 'subsidiary'),
            ['OR', ('manual_end_date', '=', None),
                ('manual_end_date', '>=', CurrentDate)]],
        'name_func': lambda x: '%s - %s' % (x.rec_name, x.parent.rec_name),
        }
    contracts = {
        'node_name': 'party.hierarchy.contracts',
        'model': 'contract',
        'main_field': 'subscriber',
        'type': 'data',
        'domain': [('status', 'not in', ['void', 'terminated'])],
        'childs': [contracts_covereds, contracts_terminated_covered_root],
        }
    contract_root = {
        'node_name': 'party.hierarchy.contract',
        'model': 'contract',
        'main_field': 'subscriber',
        'type': 'node',
        'icon': 'contract',
        'name': 'Contracts',
        'domain': [('status', 'not in', ['void', 'terminated'])],
        'childs': [contracts],
        }
    party_root = {
        'node_name': 'party.hierarchy.party',
        'model': 'party.party',
        'main_field': 'id',
        'type': 'data',
        'childs': [contract_root, terminated_contract_root, covereds,
            terminated_covered_root],
        }
    root = {
        'node_name': 'party.hierarchy',
        'type': 'root',
        'main_field': 'party.party',
        'name': 'Party Hierarchy',
        'childs': [party_root, subsidiary],
        }
    return root


def register():
    Pool.register(
        offered.Product,
        offered.OptionDescription,
        offered.ItemDesc,
        contract.Contract,
        contract.Option,
        contract.CoveredElement,
        party.Party,
        wizard.TransferCoveredElementsContracts,
        wizard.TransferCoveredElementsItemDescs,
        wizard.TransferCoveredElementsItemDescLine,
        rule_engine.RuleEngineRuntime,
        module='contract_group', type_='model')

    Pool.register(
        wizard.TransferCoveredElements,
        module='contract_group', type_='wizard')

    from trytond.modules.coog_core.hierarchy import generate_hierarchy
    models, wiz = generate_hierarchy(get_organization_hierarchy())
    Pool.register(*models,
        module='contract_group', type_='model')
    Pool.register(wiz,
        module='contract_group', type_='wizard')

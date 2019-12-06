# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'questionnaire'
    extras = ['web_configuration']

    @classmethod
    def fetch_models_for(cls):
        return ['offered', 'rule_engine']

    @classmethod
    def get_models(cls):
        return {
            'Questionnaire': 'questionnaire',
            'APICore': 'api.core',
             }

    @test_framework.prepare_test(
        'offered.test0010_testProductCreation',
        'rule_engine.test0013_createTestContext',
        )
    def test0001_init_questionnaire(self):
        product, = self.Product.search([('code', '=', 'AAA')])
        rule_context, = self.Context.search([('name', '=', 'test_context')])

        remboursement_anticipe = self.ExtraData()
        remboursement_anticipe.string = 'Envisagez-vous des remboursements ' + \
            'anticipes ?'
        remboursement_anticipe.name = 'remboursement_anticipe'
        remboursement_anticipe.type_ = 'selection'
        remboursement_anticipe.selection = 'oui: Oui\nnon: Non'
        remboursement_anticipe.kind = 'questionnaire'
        remboursement_anticipe.save()

        plusieurs_emprunteurs = self.ExtraData()
        plusieurs_emprunteurs.string = 'Y a-t-il plusieurs emprunteurs ?'
        plusieurs_emprunteurs.name = 'plusieurs_emprunteurs'
        plusieurs_emprunteurs.type_ = 'selection'
        plusieurs_emprunteurs.selection = 'oui: Oui\nnon: Non'
        plusieurs_emprunteurs.kind = 'questionnaire'
        plusieurs_emprunteurs.save()

        capitaux_eleves = self.ExtraData()
        capitaux_eleves.string = 'Souhaitez-vous des montants de capitaux ' + \
            'importants ?'
        capitaux_eleves.name = 'capitaux_eleves'
        capitaux_eleves.type_ = 'selection'
        capitaux_eleves.selection = 'oui: Oui\nnon: Non'
        capitaux_eleves.kind = 'questionnaire'
        capitaux_eleves.save()

        rule_questionnaire_loan = self.RuleEngine()
        rule_questionnaire_loan.type_ = 'questionnaire'
        rule_questionnaire_loan.context = rule_context
        rule_questionnaire_loan.status = 'validated'
        rule_questionnaire_loan.name = 'Regle questionnaire emprunteur'
        rule_questionnaire_loan.short_name = 'rule_questionnaire_loan'
        rule_questionnaire_loan.description = 'lorem ipsum'
        rule_questionnaire_loan.algorithm = '''
return [
    {
        'score': 100,
        'description': 'La meilleure solution pour vos prets',
        'product': '%s',
        'eligible': True,
        },
    {
        'score': 50,
        'description': 'Pas si mal, mais le produit n existe pas...',
        'product': 'unknown',
        'eligible': True,
        },
    {
        'score': 10,
        'description': 'La pire solution pour vos prets',
        'product': '%s',
        'eligible': False,
        },
        ]
''' % (product.code, product.code)
        rule_questionnaire_loan.save()

        rule_questionnaire_life = self.RuleEngine()
        rule_questionnaire_life.type_ = 'questionnaire'
        rule_questionnaire_life.context = rule_context
        rule_questionnaire_life.status = 'validated'
        rule_questionnaire_life.name = 'Regle questionnaire Prevoyance'
        rule_questionnaire_life.short_name = 'rule_questionnaire_life'
        rule_questionnaire_life.description = 'dolor sic amet'
        rule_questionnaire_life.algorithm = '''
return [
    {
        'score': 100,
        'description': 'La meilleure prevoyance',
        'product': '%s',
        'eligible': True,
        }]
''' % product.code
        rule_questionnaire_life.save()

        questionnaire = self.Questionnaire()
        questionnaire.name = 'Questionnaire Emprunteur / Prevoyance'
        questionnaire.code = 'questionnaire_emprunteur_prevoyance'
        questionnaire.sequence = 1
        questionnaire.company = product.company
        questionnaire.description = 'Notre algorithme a votre service'
        questionnaire.products = [product]
        questionnaire.parts = [{
                'sequence': 1,
                'name': 'Emprunteur',
                'rule': rule_questionnaire_loan.id,
                'extra_data_def': [
                    remboursement_anticipe.id, plusieurs_emprunteurs.id],
                },
            {
                'sequence': 2,
                'name': 'Prevoyance',
                'rule': rule_questionnaire_life.id,
                'extra_data_def': [capitaux_eleves.id],
                },
            ]
        questionnaire.save()

    @test_framework.prepare_test('questionnaire.test0001_init_questionnaire')
    def test0010_test_questionnaire_description_api(self):
        questionnaire, = self.Questionnaire.search([])
        remboursement_anticipe, = self.ExtraData.search([
                ('name', '=', 'remboursement_anticipe')])
        plusieurs_emprunteurs, = self.ExtraData.search([
                ('name', '=', 'plusieurs_emprunteurs')])
        capitaux_eleves, = self.ExtraData.search([
                ('name', '=', 'capitaux_eleves')])

        # Be naughty for now
        self.APICore._apis['list_questionnaires']['access_policy'] = 'public'

        self.maxDiff = None

        expected = {
            'title': questionnaire.name,
            'code': questionnaire.code,
            'id': questionnaire.id,
            'icon': '',
            'sequence': questionnaire.sequence,
            'description': questionnaire.description,
            'parts': [
                {
                    'id': questionnaire.parts[0].id,
                    'title': 'Emprunteur',
                    'mandatory': False,
                    'sequence': questionnaire.parts[0].sequence,
                    'description': 'lorem ipsum',
                    'groups': [],
                    'questions': [
                        {
                            'code': 'remboursement_anticipe',
                            'name': 'Envisagez-vous des remboursements '
                            'anticipes ?',
                            'type': 'selection',
                            'sequence':
                            remboursement_anticipe.sequence_order,
                            'selection': [
                                {'value': 'oui', 'name': 'Oui',
                                    'sequence': 0},
                                {'value': 'non', 'name': 'Non',
                                    'sequence': 1},
                                ],
                            },
                        {
                            'code': 'plusieurs_emprunteurs',
                            'name': 'Y a-t-il plusieurs emprunteurs ?',
                            'type': 'selection',
                            'sequence':
                            plusieurs_emprunteurs.sequence_order,
                            'selection': [
                                {'value': 'oui', 'name': 'Oui',
                                    'sequence': 0},
                                {'value': 'non', 'name': 'Non',
                                    'sequence': 1},
                                ],
                            },
                        ],
                    },
                {
                    'id': questionnaire.parts[1].id,
                    'title': 'Prevoyance',
                    'mandatory': False,
                    'sequence': questionnaire.parts[1].sequence,
                    'description': 'dolor sic amet',
                    'groups': [],
                    'questions': [
                        {
                            'code': 'capitaux_eleves',
                            'name': 'Souhaitez-vous des montants de '
                            'capitaux importants ?',
                            'type': 'selection',
                            'sequence': capitaux_eleves.sequence_order,
                            'selection': [
                                {'value': 'oui', 'name': 'Oui',
                                    'sequence': 0},
                                {'value': 'non', 'name': 'Non',
                                    'sequence': 1},
                                ],
                            },
                        ],
                    },
                        ],
                    }
        self.assertEqual(
            self.APICore.list_questionnaires({}, {'_debug_server': True}),
            [expected])
        self.assertEqual(
            self.APICore.list_questionnaires(
                {'questionnaires': [{'id': questionnaire.id}]},
                {'_debug_server': True}),
            [expected])
        self.assertEqual(
            self.APICore.list_questionnaires(
                {'questionnaires': [{'code': questionnaire.code}]},
                {'_debug_server': True}),
            [expected])

        self.assertEqual(
            self.APICore.list_questionnaires(
                {'questionnaires': [{'code': 'inexisting'}]}, {}).data,
            [
                {
                    'type': 'configuration_not_found',
                    'data': {'code': 'inexisting', 'model': 'questionnaire'},
                    },
                ])

    @test_framework.prepare_test('questionnaire.test0001_init_questionnaire')
    def test0015_test_questionnaire_description_sub_extra_data(self):
        product, = self.Product.search([('code', '=', 'AAA')])
        rule_questionnaire_loan, = self.RuleEngine.search([('name', '=',
                    'Regle questionnaire emprunteur')])
        rule_questionnaire_life, = self.RuleEngine.search([('name', '=',
                    'Regle questionnaire Prevoyance')])
        remboursement_anticipe, = self.ExtraData.search([('name', '=',
                    'remboursement_anticipe')])
        plusieurs_emprunteurs, = self.ExtraData.search([('name', '=',
                    'plusieurs_emprunteurs')])

        remboursement_anticipe.sub_data = [plusieurs_emprunteurs]
        remboursement_anticipe.save()

        questionnaire = self.Questionnaire()
        questionnaire.name = 'Questionnaire Emprunteur / Prevoyance'
        questionnaire.code = 'questionnaire_emprunteur_prevoyance_test'
        questionnaire.sequence = 1
        questionnaire.company = product.company
        questionnaire.description = 'Notre algorithme a votre service'
        questionnaire.products = [product]
        questionnaire.parts = [{
                'sequence': 1,
                'name': 'Emprunteur',
                'rule': rule_questionnaire_loan.id,
                'extra_data_def': [
                    remboursement_anticipe.id,
                    plusieurs_emprunteurs.id,
                    ],
                'extra_data_groups': [
                    {
                        'title': 'Premier groupe',
                        'description': 'Le premier groupe',
                        'tooltip': 'premier',
                        'sequence_order': 1,
                        'parent_model': questionnaire.id,
                        'extra_data': [remboursement_anticipe.id],
                        },
                    {
                        'title': 'Deuxième groupe',
                        'description': 'Le second groupe',
                        'tooltip': 'deuxième',
                        'sequence_order': 2,
                        'parent_model': questionnaire.id,
                        'extra_data': [plusieurs_emprunteurs.id],
                        },
                    ]
                },
            ]
        questionnaire.save()

        result = self.APICore.list_questionnaires({
                'questionnaires': [{'code':
                        'questionnaire_emprunteur_prevoyance_test'}],
                }, {'_debug_server': True})
        self.assertEqual(len(result[0]['parts'][0]['groups'][0]['extra_data']),
            1)

    @test_framework.prepare_test('questionnaire.test0001_init_questionnaire')
    def test0020_test_questionnaire_compute(self):
        questionnaire, = self.Questionnaire.search([])

        data_input = {
            'questionnaire': {'id': questionnaire.id},
            'parts': [
                {
                    'id': questionnaire.parts[0].id,
                    'answers': {
                        'remboursement_anticipe': 'oui',
                        'plusieurs_emprunteurs': 'non',
                        },
                    },
                {
                    'id': questionnaire.parts[1].id,
                    'answers': {
                        'capitaux_eleves': 'oui',
                        },
                    },
                ],
            }

        expected_output = {
            'questionnaire': questionnaire.id,
            'parts': [
                {
                    'id': questionnaire.parts[0].id,
                    'results': [
                        {
                            'score': 100,
                            'description': 'La meilleure solution pour vos '
                            'prets',
                            'product': 'AAA',
                            'eligible': True,
                            },
                        {
                            'score': 10,
                            'description': 'La pire solution pour vos '
                            'prets',
                            'product': 'AAA',
                            'eligible': False,
                            },
                        ],
                    },
                {
                    'id': questionnaire.parts[1].id,
                    'results': [
                        {
                            'score': 100,
                            'description': 'La meilleure prevoyance',
                            'product': 'AAA',
                            'eligible': True,
                            },
                        ],
                    },
                ],
            }

        # Be naughty for now
        self.APICore._apis['compute_questionnaire']['access_policy'] = 'public'

        self.maxDiff = None
        self.assertEqual(
            self.APICore.compute_questionnaire(copy.deepcopy(data_input),
                {'_debug_server': True}),
            expected_output)

        new_copy = copy.deepcopy(data_input)
        new_copy['questionnaire'] = {'code': 'unknown'}
        self.assertEqual(
            self.APICore.compute_questionnaire(new_copy, {}).data,
            [{
                    'type': 'configuration_not_found',
                    'data': {
                        'model': 'questionnaire',
                        'code': 'unknown'},
                    }])

        new_copy = copy.deepcopy(data_input)
        new_copy['parts'][0]['id'] = 250000
        self.assertEqual(
            self.APICore.compute_questionnaire(new_copy, {}).data[0],
            {
                'type': 'unknown_questionnaire_part',
                'data': {
                    'questionnaire': questionnaire.code,
                    'part_id': 250000,
                    'known_parts': [x.id for x in questionnaire.parts],
                    },
                })

        new_copy = copy.deepcopy(data_input)
        new_copy['parts'][0]['answers']['hello'] = 10
        self.assertEqual(
            self.APICore.compute_questionnaire(new_copy, {}).data,
            [{
                    'type': 'unknown_extra_data',
                    'data': {'code': 'hello'},
                    }])

    @test_framework.prepare_test(
        'offered.test0010_testProductCreation',
        'rule_engine.test0013_createTestContext',
        )
    def test0001_init_questionnaire_with_package(self):
        product, = self.Product.search([('code', '=', 'AAA')])
        rule_context, = self.Context.search([('name', '=', 'test_context')])
        pool = Pool()
        Package = pool.get('offered.package')
        PackageOptionRelation = pool.get('offered.package-option.description')

        package = Package()
        package.name = 'test package'
        package.code = 'test_package'
        relations = []
        for option in product.coverages:
            relation = PackageOptionRelation()
            relation.option = option
            relations.append(relation)
        package.option_relations = relations
        package.save()

        remboursement_anticipe = self.ExtraData()
        remboursement_anticipe.string = 'Envisagez-vous des remboursements ' + \
            'anticipes ?'
        remboursement_anticipe.name = 'remboursement_anticipe'
        remboursement_anticipe.type_ = 'selection'
        remboursement_anticipe.selection = 'oui: Oui\nnon: Non'
        remboursement_anticipe.kind = 'questionnaire'
        remboursement_anticipe.save()

        plusieurs_emprunteurs = self.ExtraData()
        plusieurs_emprunteurs.string = 'Y a-t-il plusieurs emprunteurs ?'
        plusieurs_emprunteurs.name = 'plusieurs_emprunteurs'
        plusieurs_emprunteurs.type_ = 'selection'
        plusieurs_emprunteurs.selection = 'oui: Oui\nnon: Non'
        plusieurs_emprunteurs.kind = 'questionnaire'
        plusieurs_emprunteurs.save()

        capitaux_eleves = self.ExtraData()
        capitaux_eleves.string = 'Souhaitez-vous des montants de capitaux ' + \
            'importants ?'
        capitaux_eleves.name = 'capitaux_eleves'
        capitaux_eleves.type_ = 'selection'
        capitaux_eleves.selection = 'oui: Oui\nnon: Non'
        capitaux_eleves.kind = 'questionnaire'
        capitaux_eleves.save()

        rule_questionnaire_loan = self.RuleEngine()
        rule_questionnaire_loan.type_ = 'questionnaire'
        rule_questionnaire_loan.context = rule_context
        rule_questionnaire_loan.status = 'validated'
        rule_questionnaire_loan.name = 'Regle questionnaire emprunteur'
        rule_questionnaire_loan.short_name = 'rule_questionnaire_loan'
        rule_questionnaire_loan.description = 'lorem ipsum'
        rule_questionnaire_loan.algorithm = '''
return [
    {
        'score': 100,
        'description': 'La meilleure solution pour vos prets',
        'product': '%s',
        'package': '%s',
        'eligible': True,
        },
    {
        'score': 50,
        'description': 'Pas si mal, mais le produit n existe pas...',
        'product': 'unknown',
        'package': 'unknwon',
        'eligible': True,
        },
    {
        'score': 10,
        'description': 'La pire solution pour vos prets',
        'product': '%s',
        'package': '%s',
        'eligible': False,
        },
        ]
''' % (product.code, package.code, product.code, package.code)
        rule_questionnaire_loan.save()

        rule_questionnaire_life = self.RuleEngine()
        rule_questionnaire_life.type_ = 'questionnaire'
        rule_questionnaire_life.context = rule_context
        rule_questionnaire_life.status = 'validated'
        rule_questionnaire_life.name = 'Regle questionnaire Prevoyance'
        rule_questionnaire_life.short_name = 'rule_questionnaire_life'
        rule_questionnaire_life.description = 'dolor sic amet'
        rule_questionnaire_life.algorithm = '''
return [
    {
        'score': 100,
        'description': 'La meilleure prevoyance',
        'product': '%s',
        'package': '%s',
        'eligible': True,
        }]
''' % (product.code, package.code)
        rule_questionnaire_life.save()

        questionnaire = self.Questionnaire()
        questionnaire.name = 'Questionnaire Emprunteur / Prevoyance'
        questionnaire.code = 'questionnaire_emprunteur_prevoyance'
        questionnaire.sequence = 1
        questionnaire.company = product.company
        questionnaire.description = 'Notre algorithme a votre service'
        questionnaire.products = [product]
        questionnaire.parts = [{
                'sequence': 1,
                'name': 'Emprunteur',
                'rule': rule_questionnaire_loan.id,
                'extra_data_def': [
                    remboursement_anticipe.id, plusieurs_emprunteurs.id],
                },
            {
                'sequence': 2,
                'name': 'Prevoyance',
                'rule': rule_questionnaire_life.id,
                'extra_data_def': [capitaux_eleves.id],
                },
            ]
        questionnaire.save()

    @test_framework.prepare_test('questionnaire'
        '.test0001_init_questionnaire_with_package')
    def test0020_test_questionnaire_compute_with_package(self):
        questionnaire, = self.Questionnaire.search([])

        data_input = {
            'questionnaire': {'id': questionnaire.id},
            'parts': [
                {
                    'id': questionnaire.parts[0].id,
                    'answers': {
                        'remboursement_anticipe': 'oui',
                        'plusieurs_emprunteurs': 'non',
                        },
                    },
                {
                    'id': questionnaire.parts[1].id,
                    'answers': {
                        'capitaux_eleves': 'oui',
                        },
                    },
                ],
            }

        expected_output = {
            'questionnaire': questionnaire.id,
            'parts': [
                {
                    'id': questionnaire.parts[0].id,
                    'results': [
                        {
                            'score': 100,
                            'description': 'La meilleure solution pour vos '
                            'prets',
                            'product': 'AAA',
                            'package': 'test_package',
                            'eligible': True,
                            },
                        {
                            'score': 10,
                            'description': 'La pire solution pour vos '
                            'prets',
                            'product': 'AAA',
                            'package': 'test_package',
                            'eligible': False,
                            },
                        ],
                    },
                {
                    'id': questionnaire.parts[1].id,
                    'results': [
                        {
                            'score': 100,
                            'description': 'La meilleure prevoyance',
                            'product': 'AAA',
                            'package': 'test_package',
                            'eligible': True,
                            },
                        ],
                    },
                ],
            }

        # Be naughty for now
        self.APICore._apis['compute_questionnaire']['access_policy'] = 'public'

        self.maxDiff = None
        self.assertEqual(
            self.APICore.compute_questionnaire(copy.deepcopy(data_input),
                {'_debug_server': True}),
            expected_output)

        new_copy = copy.deepcopy(data_input)
        new_copy['questionnaire'] = {'code': 'unknown'}
        self.assertEqual(
            self.APICore.compute_questionnaire(new_copy, {}).data,
            [{
                    'type': 'configuration_not_found',
                    'data': {
                        'model': 'questionnaire',
                        'code': 'unknown'},
                    }])

        new_copy = copy.deepcopy(data_input)
        new_copy['parts'][0]['id'] = 250000
        self.assertEqual(
            self.APICore.compute_questionnaire(new_copy, {}).data[0],
            {
                'type': 'unknown_questionnaire_part',
                'data': {
                    'questionnaire': questionnaire.code,
                    'part_id': 250000,
                    'known_parts': [x.id for x in questionnaire.parts],
                    },
                })

        new_copy = copy.deepcopy(data_input)
        new_copy['parts'][0]['answers']['hello'] = 10
        self.assertEqual(
            self.APICore.compute_questionnaire(new_copy, {}).data,
            [{
                    'type': 'unknown_extra_data',
                    'data': {'code': 'hello'},
                    }])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

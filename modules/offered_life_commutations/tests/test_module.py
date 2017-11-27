# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
from decimal import Decimal
import unittest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'offered_life_commutations'

    @classmethod
    def get_models(cls):
        return {
            'RuleRuntime': 'rule_engine.runtime',
            'CommutationManager': 'table.commutation_manager',
            'Table': 'table',
            }

    def test0001_commutation_values(self):
        with open(os.path.abspath(os.path.join(os.path.abspath(__file__), '..',
                        'TD-88-90.json')), 'r') as f:
            self.Table.import_json(f.read())
        manager = self.CommutationManager(
            lines=[{
                    'base_table': self.Table.search([
                            ('code', '=', 'TD-88-90')])[0],
                    'rate': Decimal('0.0075'),
                    'frequency': '1',
                    }])
        manager.save()

        values = self.CommutationManager.get_life_commutation('TD-88-90',
            Decimal('0.0075'), '1', 31)
        expected = {
            'dx': Decimal('168'),
            'qx': Decimal('0.001739184446721947886580328582'),
            'px': Decimal('0.9982608155532780521134196714'),
            'vx': Decimal('0.7932376162894413525732487509'),
            'Dx': Decimal('76624.37402071116633451810959'),
            'Cx': Decimal('132.7669734197162110346873982'),
            'Mx': Decimal('55650.43345080480987165221080'),
            'Nx': Decimal('2845376.544163764399162027858'),
            'Rx': Decimal('2369538.439195347362013183320'),
            'Ax': Decimal('0.7262758640711738753797618466'),
            'a"x': Decimal('37.13409186735638513426463453'),
            'ax': Decimal('36.13409186735638513426463453'),
            }
        for key in ('dx', 'qx', 'px', 'vx', 'Dx', 'Cx', 'Mx', 'Nx', 'Rx', 'Ax',
                'a"x', 'ax'):
            self.assertEqual(values[key], expected[key])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

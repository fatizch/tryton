#!/usr/bin/env python
import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'process'

    @classmethod
    def depending_modules(cls):
        return ['contract']

    @classmethod
    def get_models(cls):
        return {
            'Model': 'ir.model',
            'Process': 'process',
            'ProcessStep': 'process.step',
            'View': 'ir.ui.view',
            }

    def test_001_testProcessCreation(self):
        contract_model, = self.Model.search([('model', '=', 'contract')])
        contract_model.is_workflow = True
        contract_model.save()
        process = self.Process(on_model=contract_model,
            technical_name='basic_process', fancy_name="Basic Process")
        process.save()

        view_tree, = self.View.search([('name', '=', 'basic_process_tree')])
        view_form, = self.View.search([('name', '=', 'basic_process_form')])
        self.assertEqual(view_tree.arch,
            '<?xml version="1.0"?>'
            '<tree string="Basic Process">'
            '<field name="current_state"/></tree>')
        self.assertEqual([x.strip() for x in view_form.arch.split('\n')], [
                '<form string="Basic Process" col="4">',
                '<group id="process_content" xfill="1" xexpand="1" yfill="1" '
                'yexpand="1">',
                '<field name="current_state" invisible="1" ' 'readonly="1" '
                'colspan="4"/>',
                '<newline/>',
                '<newline/>',
                '<newline/>',
                '<group id="group_tech_complete" xfill="1" xexpand="1" '
                'yfill="1" yexpand="1" states="{&quot;invisible&quot;: '
                '{&quot;__class__&quot;: &quot;Bool&quot;, &quot;v&quot;: '
                '{&quot;d&quot;: &quot;&quot;, &quot;__class__&quot;: &quot;'
                'Eval&quot;, &quot;v&quot;: &quot;current_state&quot;}}}">',
                '<label id="complete_text" string="The current record '
                'completed the current process, please go ahead"/>',
                '</group>',
                '</group>',
                '<group id="process_buttons" colspan="1" col="1" xexpand="0" '
                'xfill="0" yexpand="1" yfill="1"/>',
                '<newline/>',
                '</form>', ''])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

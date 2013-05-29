#-*- coding:utf-8 -*-
import sys
import os
import datetime
DIR = os.path.abspath(os.path.normpath(os.path.join(
    __file__, '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton

from dateutil.relativedelta import relativedelta

from trytond.modules.coop_utils import test_framework
from trytond.transaction import Transaction


MODULE_NAME = os.path.basename(
    os.path.abspath(
        os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    @classmethod
    def get_module_name(cls):
        return MODULE_NAME

    @classmethod
    def depending_modules(cls):
        return ['life_contract', 'insurance_product', 'billing']

    @classmethod
    def get_models(cls):
        return {
            'Contract': 'contract.contract',
            'Party': 'party.party',
            'AddressKind': 'party.address_kind',
            'Sequence': 'ir.sequence',
            # 'BillingProcess': 'billing.billing_process',
        }

    def test0001_testPersonCreation(self):
        address_kind = self.AddressKind()
        address_kind.key = 'main'
        address_kind.name = 'Main'
        address_kind.save()

        party = self.Party()
        party.is_person = True
        party.name = 'Toto'
        party.first_name = 'titi'
        party.birth_date = datetime.date.today() + relativedelta(years=-39)
        party.gender = 'male'
        party.save()

        party, = self.Party.search([('name', '=', 'Toto')])
        self.assert_(party.id)

    @test_framework.prepare_test(
        'life_product.test0010_LifeProductCreation',
        'insurance_contract.test0001_testPersonCreation',
        )
    def _test0004_testContractCreation(self):
        '''
            Tests subscription process
        '''
        on_party, = self.Party.search([('name', '=', 'Toto')])
        on_product, = self.Product.search([('code', '=', 'AAA')])
        wizard_id, _, _ = self.SubsProcess.create()
        wizard = self.SubsProcess(wizard_id)
        wizard.transition_steps_start()
        tmp = wizard.project.check_step(
            wizard,
            wizard.process_state.cur_step_desc)
        self.assertEqual(tmp[0], False)
        self.assertEqual(wizard.project.start_date, datetime.date.today())
        wizard.project.start_date += datetime.timedelta(days=2)
        wizard.project.subscriber = on_party
        tmp = wizard.project.check_step(
            wizard,
            wizard.process_state.cur_step_desc)
        self.assertEqual(tmp[0], False)
        wizard.project.product = on_product
        tmp = wizard.project.check_step(
            wizard,
            wizard.process_state.cur_step_desc)
        self.assertEqual(tmp[0], False)
        self.assertEqual(tmp[1][0], 'Subscriber must be older than 40')

        # on_product, = self.Product.search([('code', '=', 'AAA')])
        # wizard.project.product = on_product
        # tmp = wizard.project.check_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], True)
        # wizard.transition_steps_next()
        # wizard.transition_master_step()
        # tmp = set([
        #     elem.offered.code for elem in wizard.option_selection.options])
        # self.assertEqual(len(tmp), len(on_product.coverages))
        # self.assertEqual(tmp,
        #                  set([elem.code for elem in on_product.coverages]))
        # self.assertEqual(wizard.option_selection.options[0].start_date,
        #                  wizard.project.start_date)
        # self.assertEqual(wizard.option_selection.options[1].start_date,
        #                  wizard.project.start_date +
        #                  datetime.timedelta(days=3))
        # wizard.option_selection.options[0].start_date += \
        #     datetime.timedelta(days=-4)
        # tmp = wizard.option_selection.check_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], False)
        # wizard.option_selection.options[0].start_date += \
        #     datetime.timedelta(days=5)
        # wizard.option_selection.options[1].start_date += \
        #     datetime.timedelta(days=-1)
        # tmp = wizard.option_selection.check_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], False)
        # wizard.option_selection.options[1].start_date += \
        #     datetime.timedelta(days=1)
        # tmp = wizard.option_selection.check_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], False)
        # self.assertEqual(tmp[1][0], 'GAM option not eligible :')
        # self.assertEqual(tmp[1][1], '\tSubscriber too old (max: 40)')

        # wizard.option_selection.options[3].status = 'Refused'
        # wizard.option_selection.options[1].status = 'Refused'
        # tmp = wizard.option_selection.check_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], True)
        # wizard.option_selection.options[1].status = 'active'
        # wizard.transition_steps_next()
        # wizard.transition_master_step()
        # wizard.transition_steps_previous()
        # wizard.transition_master_step()
        # wizard.transition_steps_next()
        # wizard.transition_master_step()
        # tmp = hasattr(wizard, 'extension_life')
        # self.assert_(tmp)
        # self.assertEqual(len(wizard.extension_life.covered_elements), 1)
        # covered = wizard.extension_life.covered_elements[0]
        # self.assertEqual(covered.elem_person, on_party)
        # self.assertEqual(len(covered.elem_covered_data), 3)
        # self.assertEqual(
        #     covered.elem_covered_data[0].data_start_date,
        #     wizard.project.start_date + datetime.timedelta(days=1))
        # tmp = wizard.extension_life.check_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], True)
        # tmp = wizard.extension_life.post_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], False)
        # self.assertEqual(
        #     tmp[1][0],
        #     'Toto must be older than 100')
        # wizard.transition_steps_previous()
        # wizard.transition_master_step()
        # wizard.option_selection.options[2].status = 'Refused'
        # wizard.transition_steps_next()
        # wizard.transition_master_step()
        # tmp = wizard.extension_life.check_step(
        #     wizard,
        #     wizard.process_state.cur_step_desc)
        # self.assertEqual(tmp[0], True)
        # wizard.transition_steps_next()
        # wizard.transition_master_step()

        # def print_line(line):
        #     if not hasattr(line, 'name'):
        #         return ''
        #     res = line.name
        #     if hasattr(line, 'value'):
        #         res += ' => %.2f' % line.value
        #     if hasattr(line, 'taxes') and line.taxes:
        #         res += ' (Tx : %.2f)' % line.taxes
        #     return res

        # lines = []

        # def parse_line(line, prefix=''):
        #     res = []
        #     res.append(prefix + print_line(line))
        #     if hasattr(line, 'childs') and line.childs:
        #         for sub_elem in line.childs:
        #             res += map(
        #                 lambda x: prefix + x, parse_line(sub_elem, '\t'))
        #     return res

        # for elem in wizard.summary.lines:
        #     lines += parse_line(elem)
        #     lines += ['']

        # def date_from_today(nb):
        #     from trytond.modules.coop_utils import date
        #     return date.add_day(datetime.date.today(), nb)

        # good_lines = [
        #     date_from_today(5).isoformat() + ' => 63.00 (Tx : 12.26)',
        #     '\tAlpha Coverage => 33.00 (Tx : 4.16)',
        #     '\t\tGlobal Price => 32.00 (Tx : 4.16)',
        #     '\t\t\tbase - PP => 12.00',
        #     '\t\t\ttax - TT => 4.16',
        #     '\t\t\tfee - FEE => 20.00',
        #     '\t\tMr. TOTO titi => 1.00',
        #     '\t\t\tbase - PP => 1.00',
        #     '\tBeta Coverage => 30.00 (Tx : 8.10)',
        #     '\t\tGlobal Price => 30.00 (Tx : 8.10)',
        #     '\t\t\tbase - PP => 30.00',
        #     '\t\t\ttax - TTA => 8.10',
        #     '',
        #     date_from_today(3).isoformat() + ' => 33.00 (Tx : 4.16)',
        #     '\tAlpha Coverage => 33.00 (Tx : 4.16)',
        #     '\t\tGlobal Price => 32.00 (Tx : 4.16)',
        #     '\t\t\tbase - PP => 12.00',
        #     '\t\t\ttax - TT => 4.16',
        #     '\t\t\tfee - FEE => 20.00',
        #     '\t\tMr. TOTO titi => 1.00',
        #     '\t\t\tbase - PP => 1.00',
        #     '',
        #     date_from_today(11).isoformat() + ' => 15.00',
        #     '\tAlpha Coverage => 15.00',
        #     '\t\tGlobal Price => 15.00',
        #     '\t\t\tbase - PP => 15.00',
        #     '']

        # lines.sort()
        # good_lines.sort()

        # self.maxDiff = None
        # #print lines, good_lines
        # self.assertListEqual(lines, good_lines)

        # wizard.transition_steps_complete()
        # wizard.transition_master_step()

        # contract, = self.Contract.search([('id', '=', '1')])
        # self.assert_(contract.id)

    @test_framework.prepare_test(
        'insurance_contract.test0004_testContractCreation',
    )
    def _test0010Contract(self):
        '''
            Creates product, test subscription and billing
        '''
        the_contract, = self.Contract.search([('id', '=', '1')])
        Transaction().context['active_model'] = the_contract.__name__
        Transaction().context['active_id'] = the_contract.id
        wizard_id, _, _ = self.BillingProcess.create()
        wizard = self.BillingProcess(wizard_id)
        wizard.transition_steps_start()
        wizard.bill_parameters.start_date = datetime.date.today()
        wizard.bill_parameters.end_date = datetime.date.today() \
            + datetime.timedelta(days=-10)
        wizard.transition_steps_next()
        tmp = wizard.bill_parameters.check_step(
            wizard,
            wizard.process_state.cur_step_desc)
        self.assertEqual(tmp[0], False)
        wizard.bill_parameters.start_date = the_contract.start_date
        wizard.bill_parameters.end_date = the_contract.start_date \
            + datetime.timedelta(days=90)
        tmp = wizard.bill_parameters.check_step(
            wizard,
            wizard.process_state.cur_step_desc)
        self.assertEqual(tmp[0], True)
        wizard.transition_master_step()

        def print_line(line, prefix=''):
            if not hasattr(line, 'line_name'):
                return []
            res = [prefix + line.line_name]
            if hasattr(line, 'line_kind'):
                res.append(line.line_kind)
            if hasattr(line, 'line_amount_ht'):
                res.append('%.2f' % line.line_amount_ht)
            if hasattr(line, 'line_amount_ttc') and line.line_amount_ttc:
                res.append('%.2f' % line.line_amount_ttc)
            if hasattr(line, 'line_start_date') and line.line_start_date:
                res.append('%s' % line.line_start_date)
            if hasattr(line, 'line_end_date') and line.line_end_date:
                res.append('%s' % line.line_end_date)
            final_res = [' - '.join(res)]
            for sub_line in line.line_sub_lines:
                final_res += print_line(sub_line, prefix + '\t')
            return final_res

        lines = []
        for elem in wizard.bill_display.bill_lines:
            lines += print_line(elem)

        wizard.transition_steps_complete()
        wizard.transition_master_step()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

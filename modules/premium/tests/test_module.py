from collections import defaultdict
import unittest
import datetime
import mock

import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    'Module Test Case'

    module = 'premium'

    @classmethod
    def get_models(cls):
        return {
            'Product': 'offered.product',
            'PremiumDate': 'offered.product.premium_date',
            'Contract': 'contract',
            'Option': 'contract.option',
            'Premium': 'contract.premium',
            'Fee': 'account.fee',
            'ContractFee': 'contract.fee',
            }

    def test001_premium_date_configuration(self):
        product = self.Product()
        product.premium_dates = [
            self.PremiumDate(type_='yearly_custom_date',
                custom_date=datetime.date(2010, 1, 1)),
            self.PremiumDate(type_='yearly_on_start_date'),
            ]

        contract = mock.Mock()
        period = mock.Mock()
        contract.start_date = datetime.date(2014, 02, 12)
        contract.end_date = datetime.date(2015, 4, 25)
        period.start_date = datetime.date(2014, 02, 12)
        period.end_date = datetime.date(2015, 4, 25)
        contract.activation_history = [period]
        contract.options = []
        contract.extra_datas = []

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 02, 12),
                datetime.date(2015, 01, 01), datetime.date(2015, 02, 12)])

        contract = mock.Mock()
        period = mock.Mock()
        contract.start_date = datetime.date(2014, 03, 01)
        contract.end_date = datetime.date(2015, 12, 31)
        period.start_date = datetime.date(2014, 03, 01)
        period.end_date = datetime.date(2015, 12, 31)
        contract.activation_history = [period]
        contract.options = []
        contract.extra_datas = []

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 03, 01),
                datetime.date(2015, 01, 01), datetime.date(2015, 03, 01)])

        product.premium_dates = [
            self.PremiumDate(type_='yearly_custom_date',
                custom_date=datetime.date(2014, 04, 26))]

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 03, 01),
                datetime.date(2014, 04, 26), datetime.date(2015, 04, 26)])

    def test010_store_prices(self):
        # Note : setting "id" is required so that object comparison work as
        # expected
        rated_entity_1 = self.Product()
        rated_entity_1.id = 10
        rated_entity_2 = self.Product()
        rated_entity_2.id = 20
        rated_entity_3 = self.Fee()
        rated_entity_3.id = 30

        parent_1 = self.Contract()
        parent_1.id = 100
        parent_1.final_end_date = None
        some_previous_line = self.Premium()
        some_previous_line.rated_entity = rated_entity_1
        some_previous_line.start = datetime.date(1999, 12, 14)
        some_previous_line.amount = 15
        some_previous_line.end = datetime.date(2000, 3, 3)
        some_previous_line.frequency = 'monthly'
        some_previous_line.parent = parent_1
        some_previous_line.taxes = []
        parent_1.premiums = [some_previous_line]

        parent_2 = self.Option()
        parent_2.id = 200
        parent_2.final_end_date = datetime.date(2002, 4, 16)
        parent_2.premiums = []

        parent_3 = self.ContractFee()
        parent_3.id = 200
        parent_3.premiums = []

        new_line_1 = mock.Mock()
        new_line_1.rated_entity = rated_entity_1
        new_line_1.rated_instance = parent_1
        new_line_1.amount = 10
        new_line_1.frequency = 'monthly'
        new_line_1.taxes = []

        new_line_2 = mock.Mock()
        new_line_2.rated_entity = rated_entity_1
        new_line_2.rated_instance = parent_1
        new_line_2.amount = 15
        new_line_2.frequency = 'monthly'
        new_line_2.taxes = []

        new_line_3 = mock.Mock()
        new_line_3.rated_entity = rated_entity_2
        new_line_3.rated_instance = parent_1
        new_line_3.amount = 10
        new_line_3.frequency = 'monthly'
        new_line_3.taxes = []

        new_line_4 = mock.Mock()
        new_line_4.rated_entity = rated_entity_1
        new_line_4.rated_instance = parent_2
        new_line_4.amount = 100
        new_line_4.frequency = 'monthly'
        new_line_4.taxes = []

        new_line_5 = mock.Mock()
        new_line_5.rated_entity = rated_entity_1
        new_line_5.rated_instance = parent_2
        new_line_5.amount = 20
        new_line_5.frequency = 'yearly'
        new_line_5.taxes = []

        new_line_6 = mock.Mock()
        new_line_6.rated_entity = rated_entity_2
        new_line_6.rated_instance = parent_2
        new_line_6.amount = 10
        new_line_6.frequency = 'monthly'
        new_line_6.taxes = []

        new_line_7 = mock.Mock()
        new_line_7.rated_entity = rated_entity_1
        new_line_7.rated_instance = parent_2
        new_line_7.amount = 0
        new_line_7.frequency = 'monthly'
        new_line_7.taxes = []

        new_line_8 = mock.Mock()
        new_line_8.rated_entity = rated_entity_3
        new_line_8.rated_instance = parent_3
        new_line_8.amount = 25
        new_line_8.frequency = 'at_contract_signature'
        new_line_8.taxes = []

        new_line_9 = mock.Mock()
        new_line_9.rated_entity = rated_entity_1
        new_line_9.rated_instance = parent_1
        new_line_9.amount = 50
        new_line_9.frequency = 'at_contract_signature'
        new_line_9.taxes = []

        test_data = {
            None: [new_line_8, new_line_9],
            datetime.date(2000, 4, 5): [new_line_1, new_line_6, new_line_7],
            datetime.date(2000, 3, 4): [new_line_2, new_line_4],
            datetime.date(2001, 6, 12): [new_line_5, new_line_3],
            }

        with mock.patch.object(self.Premium, 'save') as patched_save:
            self.Contract.store_prices(test_data)

            save_args = patched_save.call_args[0][0]

            # Group saved premiums per parent
            saved_premiums_by_parents = {}
            saved_premiums_by_parents = defaultdict(list)
            for premium in save_args:
                saved_premiums_by_parents[premium.parent.__name__].append(
                    premium)

            def premium_matches(premium, input_line):
                for fname in ['rated_entity', 'amount', 'frequency']:
                    if getattr(premium, fname) != getattr(input_line, fname):
                        return False
                return True

            def get_matching_premium(line):
                good_premiums = saved_premiums_by_parents[
                    line.rated_instance.__name__]
                res, = [x for x in good_premiums if premium_matches(x, line)]
                return res

            def test_matching_premium(line, expected_end=None):
                premium = get_matching_premium(line)
                self.assertEqual(premium.end, expected_end)

            # Test explanations :
            #   There are 10 input lines (9 new lines and the already existing
            #   line on parent_1). Only 8 of those are saved because :
            #     - new_line_2 is a duplicate of some_previous_line
            #     - new_line_7 amount is 0
            #
            #   The end dates are set as follow :
            #     - some_previous_line to new_line_1.start - 1
            #     - new_line_4 to new_line_7.start - 1 (because new_line_7
            #       is null)
            #     - new_line_5/6 to parent_2.end_date

            self.assertEqual(len(save_args), 8)

            saved_premiums = saved_premiums_by_parents['contract']
            self.assertEqual(len(saved_premiums), 4)

            saved_premiums = saved_premiums_by_parents[
                'contract.option']
            self.assertEqual(len(saved_premiums), 3)

            saved_premiums = saved_premiums_by_parents['contract.fee']
            self.assertEqual(len(saved_premiums), 1)

            # Test end dates
            test_matching_premium(new_line_1, expected_end=None)
            test_matching_premium(new_line_2,
                expected_end=datetime.date(2000, 4, 4))
            test_matching_premium(new_line_3, expected_end=None)
            test_matching_premium(new_line_4,
                expected_end=datetime.date(2000, 4, 4))
            test_matching_premium(new_line_5,
                expected_end=datetime.date(2002, 4, 16))
            test_matching_premium(new_line_6,
                expected_end=datetime.date(2002, 4, 16))
            self.assertRaises(ValueError, get_matching_premium, new_line_7)
            test_matching_premium(new_line_8, expected_end=None)
            test_matching_premium(new_line_9, expected_end=None)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

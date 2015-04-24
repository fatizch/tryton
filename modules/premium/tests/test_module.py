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

        parent_1 = self.Contract()
        parent_1.id = 100
        parent_1.end_date = None
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
        parent_2.end_date = datetime.date(2002, 4, 16)
        parent_2.premiums = []

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

        test_data = {
            datetime.date(2000, 4, 5): [new_line_1, new_line_6, new_line_7],
            datetime.date(2000, 3, 4): [new_line_2, new_line_4],
            datetime.date(2001, 6, 12): [new_line_5, new_line_3],
            }

        with mock.patch.object(self.Premium, 'save') as patched_save:
            self.Contract.store_prices(test_data)
            # Filter on x.parent.__name__ to regroup by parent
            save_args = sorted(patched_save.call_args[0][0],
                key=lambda x: (x.parent.__name__,) + x._get_key())

            # Test explanations :
            #   There are 8 input lines (7 new lines and the already existing
            #   line on parent_1). Only 6 of those are saved because :
            #     - new_line_2 is a duplicate of some_previous_line
            #     - new_line_7 amount is 0
            #
            #   The end dates are set as follow :
            #     - some_previous_line to new_line_1.start - 1
            #     - new_line_4 to new_line_7.start - 1 (because new_line_7
            #       is null)
            #     - new_line_5/6 to parent_2.end_date
            self.assertEqual(len(save_args), 6)
            self.assertEqual(save_args[0], some_previous_line)
            for premium_line, price_line in [
                    (save_args[1], new_line_1),
                    (save_args[2], new_line_3),
                    (save_args[3], new_line_4),
                    (save_args[4], new_line_5),
                    (save_args[5], new_line_6)]:
                self.assertIn(getattr(premium_line, 'contract', None), (
                        None, parent_1))
                self.assertIn(getattr(premium_line, 'option', None), (
                        None, parent_2))
                self.assertIsNotNone(premium_line.parent)
                for fname in ['rated_entity', 'amount', 'frequency']:
                    self.assertEqual(getattr(premium_line, fname),
                        getattr(price_line, fname))
            self.assertEqual(save_args[0].end, datetime.date(2000, 4, 4))
            self.assertEqual(save_args[3].end, datetime.date(2000, 4, 4))
            self.assertEqual(save_args[4].end, datetime.date(2002, 4, 16))
            self.assertEqual(save_args[5].end, datetime.date(2002, 4, 16))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import coog_date


__all__ = [
    'Product',
    'OptionDescriptionPremiumRule',
    'OptionDescription',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    def get_option_dates(self, dates, option):
        super(Product, self).get_option_dates(dates, option)
        if (hasattr(option, 'extra_premiums') and
                option.extra_premiums):
            for elem in option.extra_premiums:
                dates.add(elem.start_date)
                if elem.end_date:
                    dates.add(coog_date.add_day(elem.end_date, 1))

    def get_covered_element_dates(self, dates, covered_element):
        for data in covered_element.options:
            self.get_option_dates(dates, data)
        for version in covered_element.versions:
            if version.start:
                dates.add(version.start)
        if hasattr(covered_element, 'sub_covered_elements'):
            for sub_elem in covered_element.sub_covered_elements:
                self.get_covered_element_dates(dates, sub_elem)

    def get_dates(self, contract):
        dates = super(Product, self).get_dates(contract)
        for covered in contract.covered_elements:
            self.get_covered_element_dates(dates, covered)
        return dates


class OptionDescriptionPremiumRule:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description.premium_rule'

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionPremiumRule, cls).__setup__()
        cls.premium_base.selection.append(
            ('contract.covered_element', 'Covered Element'))

    @classmethod
    def get_appliable_extra_premiums(cls, rule_dict):
        return [extra for extra in rule_dict['option'].extra_premiums
            if ((extra.start_date or datetime.date.min) <= rule_dict['date'] <=
                (extra.end_date or datetime.date.max))]

    def do_calculate(self, rule_dict):
        lines = super(OptionDescriptionPremiumRule, self).do_calculate(
            rule_dict)
        base_amount = sum([x.amount for x in lines])
        for extra_premium in self.get_appliable_extra_premiums(rule_dict):
            extra_dict = rule_dict.copy()
            extra_dict['extra_premium'] = extra_premium
            extra_dict['_rated_instance'] = extra_premium
            lines.append(self._premium_result_class(
                    extra_premium.calculate_premium_amount(
                        extra_dict, base_amount),
                    extra_dict))
        return lines

    def set_line_frequencies(self, lines, rated_instance, date):
        ExtraPremium = Pool().get('contract.option.extra_premium')
        for line in lines:
            if not isinstance(line.rated_instance, ExtraPremium):
                continue
            if line.rated_instance.flat_amount_frequency:
                line.frequency = line.rated_instance.flat_amount_frequency
        super(OptionDescriptionPremiumRule, self).set_line_frequencies(
            lines, rated_instance, date)

    @classmethod
    def get_not_rated_line(cls, rule_dict, date):
        lines = super(OptionDescriptionPremiumRule, cls).get_not_rated_line(
            rule_dict, date)
        for extra_premium in cls.get_appliable_extra_premiums(rule_dict):
            extra_dict = rule_dict.copy()
            extra_dict['extra_premium'] = extra_premium
            extra_dict['_rated_instance'] = extra_premium
            lines.append(cls._premium_result_class(0, extra_dict))
        return lines


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    def get_rated_instances(self, base_instance):
        result = super(OptionDescription,
            self).get_rated_instances(base_instance)
        pool = Pool()
        Contract = pool.get('contract')
        CoveredElement = pool.get('contract.covered_element')
        if isinstance(base_instance, Contract):
            for covered_element in base_instance.covered_elements:
                result += self.get_rated_instances(covered_element)
        elif isinstance(base_instance, CoveredElement):
            covered = False
            for option in base_instance.options:
                if option.coverage == self:
                    result += self.get_rated_instances(option)
                    covered = True
            if covered:
                result.append(base_instance)
        return result

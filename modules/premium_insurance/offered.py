import datetime

from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import coop_date


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescriptionPremiumRule',
    'OptionDescription',
    ]


class Product:
    __name__ = 'offered.product'

    def get_contract_dates(self, dates, contract):
        super(Product, self).get_contract_dates(dates, contract)
        if contract.next_renewal_date:
            dates.add(contract.next_renewal_date)
            if not contract.end_date:
                return
            # Calculate every anniversary date until contrat termination
            cur_date = contract.next_renewal_date
            while cur_date <= contract.end_date:
                dates.add(cur_date)
                cur_date = coop_date.add_year(cur_date, 1)
        return dates

    def get_option_dates(self, dates, option):
        super(Product, self).get_option_dates(dates, option)
        if (hasattr(option, 'extra_premiums') and
                option.extra_premiums):
            for elem in option.extra_premiums:
                dates.add(elem.start_date)

    def get_covered_element_dates(self, dates, covered_element):
        for data in covered_element.options:
            self.get_option_dates(dates, data)
        if hasattr(covered_element, 'sub_covered_elements'):
            for sub_elem in covered_element.sub_covered_elements:
                self.get_covered_element_dates(dates, sub_elem)

    def get_dates(self, contract):
        dates = super(Product, self).get_dates(contract)
        for covered in contract.covered_elements:
            self.get_covered_element_dates(dates, covered)
        if self.premium_dates:
            premium_date_configuration = self.premium_dates[0]
            dates.update(premium_date_configuration.get_dates_for_contract(
                    contract))
        return dates


class OptionDescriptionPremiumRule:
    __name__ = 'offered.option.description.premium_rule'

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionPremiumRule, cls).__setup__()
        cls.premium_base.selection.append(
            ('contract.covered_element', 'Covered Element'))

    def get_appliable_extra_premiums(self, rule_dict):
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
            lines.append(self._premium_result_class(
                    extra_premium.calculate_premium_amount(
                        extra_dict, base_amount),
                    extra_dict))
        return lines


class OptionDescription:
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

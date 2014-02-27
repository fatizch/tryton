from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'CoveredData',
    ]


class Contract:
    __name__ = 'contract'

    def set_subscriber_as_covered_element(self):
        CoveredElement = Pool().get('contract.covered_element')
        item_descs = CoveredElement.get_possible_item_desc(self)
        if len(item_descs) != 1:
            return True
        item_desc = item_descs[0]
        subscriber = self.get_policy_owner(self.start_date)

        for covered_element in getattr(self, 'covered_elements', []):
            if covered_element.party == subscriber:
                return True

        if (subscriber.is_person and item_desc.kind == 'person'
                or subscriber.is_company and item_desc.kind == 'company'
                or item_desc.kind == 'party'):
            #Delete previous covered element
            CoveredElement.delete(self.covered_elements)

            covered_element = CoveredElement()
            covered_element.party = subscriber
            covered_element.start_date = self.start_date
            covered_element.item_desc = item_desc
            covered_element.main_contract = self
            cov_as_dict = covered_element.on_change_item_desc()
            for key, val in cov_as_dict.iteritems():
                setattr(covered_element, key, val)
            if not getattr(self, 'covered_elements', None):
                self.covered_elements = [covered_element]
            else:
                self.covered_elements = list(self.covered_elements)
                self.covered_elements.append(covered_element)
        return True


class CoveredData:
    __name__ = 'contract.covered_data'

    coverage_amount_selection = fields.Function(
        fields.Selection('get_possible_amounts', 'Coverage Amount',
            depends=['option', 'start_date', 'coverage_amount',
                'with_coverage_amount'], sort=False,
            states={
                'invisible': ~Eval('with_coverage_amount'),
                # 'required': ~~Eval('with_coverage_amount'),
                }),
        'get_coverage_amount_selection', 'setter_void')

    @classmethod
    def __setup__(cls):
        super(CoveredData, cls).__setup__()
        cls._error_messages.update({
                'coverage_amount_needed': 'A coverage amount must be provided',
                })

    @fields.depends('option', 'start_date', 'covered_element', 'currency')
    def get_possible_amounts(self):
        return super(CoveredData, self).get_possible_amounts()

    def get_coverage_amount_selection(self, name):
        if (hasattr(self, 'coverage_amount') and self.coverage_amount):
            # return '%.2f' % self.coverage_amount
            return self.currency.amount_as_string(self.coverage_amount)
        return ''

    @fields.depends('coverage_amount', 'coverage_amount_selection', 'currency')
    def on_change_coverage_amount_selection(self):
        if not utils.is_none(self, 'coverage_amount_selection'):
            return {'coverage_amount':
                self.currency.get_amount_from_string(
                    self.coverage_amount_selection)}
        else:
            return {'coverage_amount': None}

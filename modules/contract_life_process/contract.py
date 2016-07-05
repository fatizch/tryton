# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    def set_subscriber_as_covered_element(self):
        item_descs = self.product.item_descriptors
        if len(item_descs) != 1 or not self.subscriber:
            return True
        item_desc = item_descs[0]
        subscriber = self.get_policy_owner(self.start_date)
        covered_elements = getattr(self, 'covered_elements', [])
        if covered_elements:
            return True
        covered_elements = []
        if (subscriber.is_person and item_desc.kind == 'person'
                or subscriber.is_company and item_desc.kind == 'company'
                or item_desc.kind == 'party'):
            CoveredElement = Pool().get('contract.covered_element')
            covered_element = CoveredElement()
            covered_element.party = subscriber
            covered_element.item_desc = item_desc
            covered_element.contract = self
            covered_element.parent = None
            covered_element.versions = [Pool().get(
                    'contract.covered_element.version').get_default_version()]
            covered_element.recalculate()
            covered_elements.append(covered_element)
        self.covered_elements = covered_elements
        return True

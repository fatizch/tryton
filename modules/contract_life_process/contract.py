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
        for covered_element in getattr(self, 'covered_elements', []):
            if covered_element.party == subscriber:
                return True
        if (subscriber.is_person and item_desc.kind == 'person'
                or subscriber.is_company and item_desc.kind == 'company'
                or item_desc.kind == 'party'):
            # Delete previous covered element
            CoveredElement = Pool().get('contract.covered_element')
            CoveredElement.delete(self.covered_elements)
            covered_element = CoveredElement()
            covered_element.party = subscriber
            covered_element.start_date = self.start_date
            covered_element.item_desc = item_desc
            covered_element.main_contract = self
            covered_element.product = self.product
            covered_element.on_change_item_desc()
            if not getattr(self, 'covered_elements', None):
                self.covered_elements = [covered_element]
            else:
                self.covered_elements = list(self.covered_elements)
                self.covered_elements.append(covered_element)
        return True

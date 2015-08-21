from trytond.pool import PoolMeta

from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'ContractOption',
    ]


class ContractOption:
    __name__ = 'contract.option'

    def is_item_covered(self, loss):
        res = super(ContractOption, self).is_item_covered(loss)
        if not loss.get_covered_person() or not self.covered_element:
            return res
        return res and utils.is_effective_at_date(
            self.covered_element, loss.get_date()) and \
            self.covered_element.is_party_covered(
                loss.get_covered_person(), loss.get_date())

from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import utils, fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'Option',
    ]


class Contract:
    __name__ = 'contract'

    claims = fields.Function(
        fields.Many2Many('claim', None, None, 'Claims'),
        'get_claims')

    def get_claims(self, name):
        Service = Pool().get('claim.service')
        services = Service.search(['contract', '=', self.id])
        return [service.loss.claim.id for service in services]

    def get_possible_benefits(self, loss):
        res = []
        for option in self.options:
            res.extend(option.get_possible_benefits(loss))
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                res.extend(option.get_possible_benefits(loss))
        return list(set(res))


class Option:
    __name__ = 'contract.option'

    benefits = fields.Function(
        fields.Many2Many('benefit', None, None, 'Benefits'),
        'get_benefits_ids')

    def is_item_covered(self, loss):
        return utils.is_effective_at_date(self, at_date=loss.get_date())

    def get_possible_benefits(self, loss):
        res = []
        if not self.is_item_covered(loss):
            return res
        loss_desc = loss.loss_desc if hasattr(loss, 'loss_desc') else None
        event_desc = loss.event_desc if hasattr(loss, 'event_desc') else None
        return self.coverage.get_possible_benefits(loss_desc, event_desc,
            loss.get_date())

    def get_benefits_ids(self, name):
        return [x.id for x in self.coverage.benefits] if self.coverage else []

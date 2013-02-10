from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.modules.coop_utils import utils, model

from trytond.modules.process import ClassAttr


__all__ = [
    'ClaimProcess',
    'LossProcess',
]


class ClaimProcess():
    'Claim'

    __name__ = 'ins_claim.claim'
    __metaclass__ = ClassAttr

    contracts = fields.Function(
        fields.One2Many('ins_contract.contract', None, 'Contracts',
            on_change_with=['claimant']),
        'on_change_with_contracts')

    def get_possible_contracts(self):
        if not self.claimant:
            return []
        Contract = Pool().get('ins_contract.contract')
        return Contract.search([('subscriber', '=', self.claimant.id)])

    def on_change_with_contracts(self, name=None):
        return [x.id for x in self.get_possible_contracts()]

    def init_delivered_services(self):
        Option = Pool().get('ins_contract.option')
        for loss in self.losses:
            for option_id, benefits in loss.get_possible_benefits().items():
                loss.init_delivered_services(Option(option_id), benefits)
            #Why do we need to save now?
            loss.save()
        return True


class LossProcess():
    'Loss'

    __name__ = 'ins_claim.loss'
    __metaclass__ = PoolMeta

    benefits = fields.Function(
        fields.One2Many('ins_product.benefit', None, 'Benefits',
            on_change_with=['loss_desc', 'event_desc', 'start_date', 'claim']),
        'on_change_with_benefits')

    def get_possible_benefits(self):
        if not self.claim or not self.loss_desc:
            return {}
        res = {}
        for contract in self.claim.get_possible_contracts():
            for option in contract.options:
                benefits = option.offered.get_possible_benefits(
                    self.loss_desc, self.event_desc, self.start_date)
                if benefits:
                    res[option.id] = benefits
        return res

    def on_change_with_benefits(self, name=None):
        res = []
        for x in self.get_possible_benefits().values():
            res += [benefit.id for benefit in x]
        return list(set(res))

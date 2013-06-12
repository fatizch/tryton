from trytond.pool import PoolMeta

__all__ = [
    'Contract',
    ]


class Contract():
    'Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    def get_protocol_offered(self, kind):
        dist_network = self.get_dist_network()
        if kind != 'commission' or not dist_network:
            return super(Contract, self).get_protocol(kind)
        coverages = [x.offered for x in self.options]
        for comp_plan in [x for x in dist_network.all_com_plans
                if not x.end_date or x.end_date >= self.start_date]:
            compensated_cov = []
            for comp in comp_plan.coverages:
                compensated_cov.extend(comp.coverages)
            if set(coverages).issubset(set(compensated_cov)):
                return comp_plan

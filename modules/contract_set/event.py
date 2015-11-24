from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __name__ = 'event.type.action'

    def get_contracts_from_object(self, object_):
        contracts = super(EventTypeAction,
            self).get_contracts_from_object(object_)
        if object_.__name__ == 'contract.set':
            contracts.extend(object_.contracts)
        return contracts

    def get_contract_sets_from_object(self, object_):
        contract_sets = []
        if object_.__name__ == 'contract.set':
            contract_sets = [object_]
        elif object_.__name__ == 'contract':
            if object_.contract_set:
                contract_sets = [object_.contract_set]
        else:
            contracts = self.get_contracts_from_object(object_)
            if contracts:
                contract_sets = self.get_contract_sets_from_object(
                    contracts[0])
        return contract_sets

    def get_targets_and_origin_from_object_and_template(self,
            object_, template):
        if template.on_model and template.on_model.model == 'contract.set':
            contract_sets = self.get_contract_sets_from_object(object_)
            if contract_sets:
                return contract_sets, self.get_report_origin(object_, template)
        return super(EventTypeAction,
            self).get_targets_and_origin_from_object_and_template(object_,
                template)

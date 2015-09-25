from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    ]


class Event:
    __name__ = 'event'

    @classmethod
    def get_contracts_from_object(cls, object_):
        contracts = super(Event, cls).get_contracts_from_object(object_)
        if object_.__name__ == 'contract.set':
            contracts.extend(object_.contracts)
        res = []
        for contract in contracts:
            res.extend(contract.contract_set.contracts)
        return list(set(res))

    @classmethod
    def get_contract_sets_from_object(cls, object_):
        contract_sets = []
        if object_.__name__ == 'contract.set':
            contract_sets = [object_]
        elif object_.__name__ == 'contract':
            if object_.contract_set:
                contract_sets = [object_.contract_set]
        else:
            contracts = cls.get_contracts_from_object(object_)
            if contracts:
                contract_sets = cls.get_contract_sets_from_object(contracts[0])
        return contract_sets

    @classmethod
    def get_targets_and_origin_from_object_and_template(cls,
            object_, template):
        if template.on_model and template.on_model.model == 'contract.set':
            contract_sets = cls.get_contract_sets_from_object(object_)
            if contract_sets:
                return contract_sets, object_
        return super(Event,
            cls).get_targets_and_origin_from_object_and_template(object_,
                template)

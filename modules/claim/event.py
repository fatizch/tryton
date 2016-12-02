# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'EventLog',
    ]


class EventLog:
    __metaclass__ = PoolMeta
    __name__ = 'event.log'

    claim = fields.Many2One('claim', 'Claim', ondelete='SET NULL', select=True)

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'contract':
            if object_.__name__ == 'claim':
                return [object_.get_contract()]
            if object_.__name__ == 'claim.loss':
                return [object_.claim.get_contract()]
            if object_.__name__ == 'claim.service':
                return [object_.contract]
        if model_name == 'claim':
            if object_.__name__ == 'claim':
                return [object_]
            if object_.__name__ == 'claim.loss':
                return [object_.claim]
            elif object_.__name__ == 'claim.service':
                return [object_.claim]
            else:
                return []
        return super(EventLog, cls).get_related_instances(object_, model_name)

    @classmethod
    def get_event_keys(cls, objects):
        cur_dicts = super(EventLog, cls).get_event_keys(objects)
        for object_, log_dicts in cur_dicts.items():
            claims = [x for x in
                cls.get_related_instances(object_, 'claim') if x]
            if not claims:
                continue
            new_dicts = []
            for log_dict in log_dicts:
                for claim in claims:
                    new_dict = log_dict.copy()
                    new_dict['claim'] = claim.id
                    new_dicts.append(new_dict)
            cur_dicts[object_] = new_dicts
        return cur_dicts

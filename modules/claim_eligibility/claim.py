from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Loss',
    ]


class Loss:
    __name__ = 'claim.loss'

    def init_service(self, option, benefit):
        exec_context = {}
        self.init_dict_for_rule_engine(exec_context)
        exec_context['option'] = option
        exec_context['date'] = self.start_date
        if not benefit.check_eligibility(exec_context):
            return
        return super(Loss, self).init_service(option, benefit)

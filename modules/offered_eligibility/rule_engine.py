from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngine',
    ]


class RuleEngine:
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('eligibility', 'Eligibility'))

    def on_change_with_result_type(self, name=None):
        if self.type_ == 'eligibility':
            return 'boolean'
        return super(RuleEngine, self).on_change_with_result_type(name)

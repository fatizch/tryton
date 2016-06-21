from trytond.pool import PoolMeta

__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_portfolio_code(cls, args):
        portfolio = args['contract'].subscriber.portfolio
        return portfolio.code if portfolio else ''

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model

__all__ = [
    'Configuration',
    'ConfigurationDefaultDunningProcedure',
    'MoveLine',
    ]


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._function_auto_cache_fields.append('default_dunning_procedure')


class ConfigurationDefaultDunningProcedure(model.ConfigurationMixin):
    __name__ = 'account.configuration.default_dunning_procedure'


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    inactive_dunnings = fields.One2ManyDomain('account.dunning', 'line',
        'Inactive Dunnings', domain=[('active', '=', False)],
         target_not_required=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls.dunnings.states['invisible'] = ~Eval('dunnings')

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('inactive_dunnings', None)
        return super(MoveLine, cls).copy(lines, default=default)

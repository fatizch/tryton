# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import model


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            {
                'button_recompute_period': {
                    'invisible': Eval('status').in_(['quote'])
                    },
            })

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [(
            '/form/group[@id="third_party_buttons"]',
            'states',
            {'invisible': True}
            )]

    @classmethod
    @model.CoogView.button_action(
        'third_party_right_management.wizard_recompute_period')
    def button_recompute_period(cls, contracts):
        pass

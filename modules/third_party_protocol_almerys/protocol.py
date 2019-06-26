# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


class Protocol(metaclass=PoolMeta):
    __name__ = 'third_party_manager.protocol'

    ALMERYS_STATES = {
        'required': Eval('technical_protocol') == 'almerys',
        'invisible': Eval('technical_protocol') != 'almerys',
        }
    ALMERYS_DEPENDS = ['technical_protocol']

    almerys_ss_groupe = fields.Char("Numéro Sous-Groupe",
        states=ALMERYS_STATES, depends=ALMERYS_DEPENDS)
    almerys_libelle_ss_groupe = fields.Char("Libellé Numéro Sous-Groupe",
        states=ALMERYS_STATES, depends=ALMERYS_DEPENDS)
    almerys_support_tp = fields.Boolean("Support Tiers-Payant",
        states={
            'invisible': Eval('technical_protocol') != 'almerys',
            },
        depends=ALMERYS_DEPENDS)

    del ALMERYS_STATES, ALMERYS_DEPENDS

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.technical_protocol.selection.append(('almerys', 'Almerys'))

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ("/form/notebook/page[@id='almerys']", 'states', {
                    'invisible': Eval('technical_protocol') != 'almerys',
                    }),
            ]

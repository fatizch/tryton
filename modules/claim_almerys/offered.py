# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    almerys_management = fields.Boolean("Almerys Management")
    almerys_benefit_tp = fields.Many2One(
        'benefit', "Third Party Payment Benefit", ondelete='RESTRICT',
        domain=[
            ('insurer', '=', Eval('insurer', -1)),
            ],
        states={
            'invisible': ~Eval('almerys_management', False),
            'required': Eval('almerys_management', False),
            },
        depends=['insurer', 'almerys_management'])
    almerys_benefit_htp = fields.Many2One('benefit', "Standard Benefit",
        ondelete='RESTRICT',
        domain=[
            ('insurer', '=', Eval('insurer', -1)),
            ],
        states={
            'invisible': ~Eval('almerys_management', False),
            'required': Eval('almerys_management', False),
            },
        depends=['insurer', 'almerys_management'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if 'invisible' in cls.benefits.states:
            cls.benefits.states['invisible'] |= Eval(
                'almerys_management', False)
        else:
            cls.benefits.states['invisible'] = Eval('almerys_management', False)
        cls.benefits.depends.append('almerys_management')

    @fields.depends('insurer', 'almerys_management')
    def on_change_almerys_management(self):
        pool = Pool()
        Benefit = pool.get('benefit')

        if not self.almerys_management or not self.insurer:
            self.almerys_benefit_htp = None
            self.almerys_benefit_tp = None
            return

        benefits = {b.code.split('_')[0]: b
            for b in Benefit.search([
                    ('insurer', '=', self.insurer.id),
                    ('code', 'in', ['{}_{}'.format(k, self.insurer.party.code)
                            for k in ('TP', 'HTP')]),
                    ],
                order=[('code', 'DESC')])}
        self.almerys_benefit_htp = benefits.get('HTP')
        self.almerys_benefit_tp = benefits.get('TP')

    def get_possible_benefits(self, loss_desc=None, event_desc=None,
            at_date=None):
        if not self.almerys_management:
            return super().get_possible_benefits(loss_desc, event_desc, at_date)
        benefits = []
        for benefit in {self.almerys_benefit_tp, self.almerys_benefit_htp}:
            if not loss_desc or loss_desc in benefit.loss_descs:
                benefits.append(benefit)
        return benefits

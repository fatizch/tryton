# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Equal, Not

from trytond.modules.coog_core import model, fields
from trytond.modules.currency_cog.currency import DEF_CUR_DIG

__all__ = [
    'Loss',
    'Service',
    'IndemnificationDetail',
    'HospitalisationPeriod',
    ]


class Loss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss'

    hospitalisation_periods = fields.One2Many(
        'claim.loss.hospitalisation.period', 'loss',
        'Hospitalisation Periods', states={
            'invisible': Not(Equal(Eval('loss_desc_kind'), 'std'))},
        depends=['loss_desc_kind'])

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls._error_messages.update({
                'period_overlap': 'There are overlapping periods',
                })

    @classmethod
    def validate(cls, losses_desc):
        super(Loss, cls).validate(losses_desc)

        def is_date_between_or_after(date, start_date, end_date):
            if (date > start_date and date < end_date) or date > end_date:
                return True
            return False

        for loss in losses_desc:
            if len(loss.hospitalisation_periods) <= 1:
                continue
            periods = [(x.start_date, x.end_date)
                for x in loss.hospitalisation_periods]
            periods = sorted(periods, key=lambda x: x[0])
            for idx, period in enumerate(periods):
                if idx + 1 < len(periods):
                    # Check that we have no overlapping dates
                    if is_date_between_or_after(period[0], periods[idx + 1][0],
                            periods[idx + 1][1]) or is_date_between_or_after(
                                period[1], periods[idx + 1][0],
                                periods[idx + 1][1]):
                        cls.raise_user_error('period_overlap')


class Service:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def get_theoretical_covered_element(self, name):
        # This should be in a claim_group_life module which does not exist
        if (self.option and self.option.is_group and
                self.option.covered_element):
            person = self.get_covered_person()
            if person and self.option.covered_element.party != person:
                for elem in self.option.covered_element.sub_covered_elements:
                    if elem.party == person:
                        return elem
        return super(Service, self).get_theoretical_covered_element(name)


class IndemnificationDetail:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification.detail'

    part_time_amount = fields.Numeric('Part Time Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])

    @classmethod
    def __setup__(cls):
        super(IndemnificationDetail, cls).__setup__()
        cls.kind.selection.append(('part_time', 'Part Time'))


class HospitalisationPeriod(model.CoogSQL, model.CoogView):
    """HospitalisationPeriod"""

    __name__ = 'claim.loss.hospitalisation.period'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    loss = fields.Many2One('claim.loss', 'Loss', ondelete="CASCADE")

    @classmethod
    def __setup__(cls):
        super(HospitalisationPeriod, cls).__setup__()
        cls._error_messages.update({
                'invalid_period': 'The period is invalid',
                })

    @classmethod
    def validate(cls, periods):
        super(HospitalisationPeriod, cls).validate(periods)
        for period in periods:
            if period.start_date > period.end_date or \
                    (period.loss.start_date and period.start_date <
                        period.loss.start_date) or \
                    (period.end_date and period.loss.end_date and
                        period.end_date > period.loss.end_date):
                cls.raise_user_error('invalid_period')

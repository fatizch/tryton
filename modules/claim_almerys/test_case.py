# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from operator import attrgetter

from trytond.pool import Pool, PoolMeta
from trytond.modules.coog_core import fields, model


class TestCaseModel(metaclass=PoolMeta):
    __name__ = 'ir.test_case'

    almerys_insurers = fields.Many2Many(
        'test_case-almerys.insurer', 'case', 'insurer', "Almerys Insurers")
    almerys_benefit_start_date = fields.Date("Almerys Benefit Start Date")

    @classmethod
    def almerys_descriptions_test_case(cls):
        pool = Pool()
        LossDesc = pool.get('benefit.loss.description')
        EventDesc = pool.get('benefit.event.description')
        Benefit = pool.get('benefit')
        Option = pool.get('offered.option.description')

        company = cls.get_company()

        if LossDesc.search([('code', '=', 'TP')]):
            return

        losses, events = {}, {}
        losses['tp'] = LossDesc(
            code='TP',
            name='Tiers Payant',
            company=company,
            has_end_date=False,
            loss_kind='health',
            item_kind='person')
        losses['htp'] = LossDesc(
            code='HTP',
            name='Hors Tiers Payant',
            company=company,
            has_end_date=False,
            loss_kind='health',
            item_kind='person')
        LossDesc.save(list(losses.values()))

        events['tp'] = EventDesc(
            code='TP',
            name='Tiers Payant',
            loss_descs=[losses['tp']],
            company=company,
            sequence=100)
        events['htp'] = EventDesc(
            code='HTP',
            name='Hors Tiers Payant',
            loss_descs=[losses['htp']],
            company=company,
            sequence=200)
        EventDesc.save(list(events.values()))

        test_case = cls(1)
        benefits = {}
        for insurer in test_case.almerys_insurers:
            for kind in ('tp', 'htp'):
                benefits[(insurer.id, kind)] = Benefit(
                    automatic_period_calculation=False,
                    automatically_deliver=True,
                    beneficiary_kind='subscriber',
                    code=kind.upper() + '_' + insurer.party.code,
                    company=company,
                    indemnification_kind='capital',
                    insurer=insurer,
                    loss_descs=[losses[kind]],
                    may_have_origin=False,
                    name=('Hors ' if kind == 'htp' else '') + 'Tiers Payant',
                    start_date=test_case.almerys_benefit_start_date,
                    delegation=(
                        'prestation' if kind == 'htp'
                        else 'prestation_reimbursement'),
                    )
        if benefits:
            Benefit.save(benefits.values())

        almerys_options = Option.search([
                ('almerys_management', '=', True),
                ('almerys_benefit_tp', '=', None),
                ('almerys_benefit_htp', '=', None),
                ],
            order=[('insurer', 'ASC')])
        for insurer_id, options in groupby(
                almerys_options, attrgetter('insurer.id')):
            for option in almerys_options:
                option.almerys_benefit_tp = benefits[(insurer_id, 'tp')]
                option.almerys_benefit_htp = benefits[(insurer_id, 'htp')]
        Option.save(almerys_options)


class TestCaseAlmerysInsurer(model.CoogSQL):
    "Test Case - Almerys Insurer"
    __name__ = 'test_case-almerys.insurer'

    case = fields.Many2One('ir.test_case', "Case",
        required=True, ondelete='CASCADE')
    insurer = fields.Many2One('insurer', "Insurer",
        required=True, ondelete='CASCADE')

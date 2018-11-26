# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import configuration
from . import ir
from . import report_engine
from . import user_analytic
from . import wizard


def register():
    Pool.register(
        configuration.Configuration,
        ir.Session,
        report_engine.ReportTemplate,
        user_analytic.UserConnection,
        user_analytic.DailyConnection,
        user_analytic.DailyGlobalConnection,
        user_analytic.MonthlyGlobalConnection,
        wizard.ConnectionDateSelector,
        module='user_analytics', type_='model')
    Pool.register(
        wizard.WizardConnection,
        module='user_analytics', type_='wizard')

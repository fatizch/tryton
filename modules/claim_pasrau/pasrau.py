# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from lxml import etree
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from trytond.pyson import Eval
from trytond.model import Unique
from trytond.pool import Pool

from trytond.modules.coog_core import model, fields, coog_date

__all__ = [
    'PartyCustomPasrauRate',
    'DefaultPasrauRate',
    ]

MONTH_FROM_STR = {
    'JANVIER': 1,
    'FEVRIER': 2,
    'MARS': 3,
    'AVRIL': 4,
    'MAI': 5,
    'JUIN': 6,
    'JUILLET': 7,
    'AOUT': 8,
    'SEPTEMBRE': 9,
    'OCTOBRE': 10,
    'NOVEMBRE': 11,
    'DECEMBRE': 12,
    }


class PartyCustomPasrauRate(model.CoogSQL, model.CoogView):
    'Party Custom Pasrau Rate'
    __name__ = 'party.pasrau.rate'

    effective_date = fields.Date('Effective date', required=True, select=True)
    pasrau_tax_rate = fields.Numeric('Pasrau tax rate', digits=(16, 4),
        required=True)
    origin = fields.Selection([
            ('default', 'Default'),
            ('manual', 'Manual')], 'Origin')
    party = fields.Many2One('party.party', 'Party', required=True,
       ondelete='CASCADE', select=True)

    @classmethod
    def __setup__(cls):
        super(PartyCustomPasrauRate, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('party_date_unique', Unique(t, t.party, t.effective_date),
                'The rate must be unique per party / date'),
            ]

    @classmethod
    def default_origin(cls):
        return 'manual'

    @classmethod
    def process_xml_file(cls, path, logger=None):
        pool = Pool()
        Party = pool.get('party.party')
        return_bool = False
        with open(path, 'r') as f:
            root_element = etree.fromstring(f.read())
            if root_element is None:
                return False

            def node_func(base, key, value=False):
                node = base.xpath('%s' % key)
                if not node:
                    return None
                if not value:
                    return node
                return node[0].text

            to_save = []
            for declaration in node_func(root_element, 'declaration'):
                for declaration_identification in node_func(declaration,
                        'declaration_identification'):
                    identifiant_metier = node_func(declaration_identification,
                        'identifiant_metier', True)
                    _month_year_str = identifiant_metier.replace(" ", "")
                    month_year_str = _month_year_str.upper()
                    lmonth_year = month_year_str.split('-')
                    assert len(lmonth_year) == 2
                    month = MONTH_FROM_STR[lmonth_year[0]]
                    year = int(lmonth_year[1])
                    effective_date = datetime.date(year, month, 1)
                    assert effective_date
                for declaration_bilan in node_func(declaration,
                        'declaration_bilan'):
                    for salarie in node_func(declaration_bilan, 'salarie'):
                        ssn = node_func(salarie, 'NIR', True)
                        if not ssn:
                            if logger:
                                logger.warning('No NIR provided')
                            continue
                        pasrau_tax_rate = node_func(salarie,
                            'taux_imposition_PAS', True)
                        party = Party.search([
                                ('ssn', '=', ssn)
                                ])
                        if not party:
                            if logger:
                                logger.warning(
                                    'No party found for NIR %s' % ssn)
                            continue
                        if not pasrau_tax_rate:
                            if logger:
                                logger.warning('No pasrau rate provided for NIR'
                                    ' %s' % ssn)
                            continue
                        rate = party[0].update_pasrau_rate(effective_date,
                            Decimal(pasrau_tax_rate) / Decimal(100))
                        if rate:
                            to_save.append(rate)
            if to_save:
                cls.save(to_save)
            return_bool = True
        return return_bool


class DefaultPasrauRate(model.CoogSQL, model.CoogView):
    'Default Pasrau Rate'
    __name__ = 'claim.pasrau.default.rate'

    start_date = fields.Date('Start Date', required=True, select=True)
    end_date = fields.Date('End Date', required=True, select=True)
    income_lower_bound = fields.Numeric('Income Lower Bound', digits=(16, 2),
        select=True, states={'required': ~Eval('income_higher_bound')},
        depends=['income_higher_bound'])
    income_higher_bound = fields.Numeric('Income Higher Bound', digits=(16, 2),
        select=True, states={'required': ~Eval('income_lower_bound')},
        depends=['income_lower_bound'])
    region = fields.Selection([
            ('metropolitan', 'Metropolitan France'),
            ('grm', 'Guadeloupe, Reunion, Martinique'),
            ('gm', 'Guyane, Mayotte')],
        'Region', required=True, select=True)
    rate = fields.Numeric('Rate', digits=(16, 4), required=True,
        select=True)

    @classmethod
    def __setup__(cls):
        super(DefaultPasrauRate, cls).__setup__()
        cls._error_messages.update({
                'no_pasrau_region': 'Unable to find PASRAU region '
                'for zip code %s',
                'no_default_pasrau': 'Could not compute a default pasrau '
                'value for parameters:\n\nZip: %(zip)s\nIncome: %(income)s\n'
                'Start: %(start)s\nEnd: %(end)s\n'
                'Invoice Date: %(invoice_date)s',
                })

    @classmethod
    def get_region(cls, zip_code):
        if 1 <= int(zip_code[:2]) <= 95:
            return 'metropolitan'
        mapping = {
            'grm': ('971', '974', '972'),
            'gm': ('973', '976')
            }
        for key, prefixes in mapping.iteritems():
            if any(zip_code.startswith(prefix) for prefix in prefixes):
                return key
        cls.raise_user_error('no_pasrau_region', zip_code)

    @classmethod
    def get_appliable_default_pasrau_rate(cls, zip_code, income, period_start,
            period_end, invoice_date):
        assert period_start and period_end
        assert period_end >= period_start
        region = cls.get_region(zip_code)

        nb_months = coog_date.number_of_months_between(period_start, period_end)

        new_start = period_start + relativedelta(months=nb_months)

        nb_days = min(max(coog_date.number_of_days_between(
                new_start, period_end,), 0), 26)

        coeff = nb_months + (Decimal(nb_days) / Decimal(26))

        monthly_income = Decimal(income) / coeff

        candidates = cls.search([
                ('region', '=', region),
                ('start_date', '<=', invoice_date),
                ('end_date', '>=', invoice_date),
                ])

        def keyfunc(x):
            return (x.start_date, x.income_lower_bound or 0)

        candidates = sorted(candidates, key=keyfunc)

        for candidate in candidates:
            if monthly_income < (candidate.income_higher_bound or
                    Decimal('10e9')):
                return candidate.rate
        cls.raise_user_error('no_default_pasrau', {
                'zip': zip_code,
                'income': '%.2f' % income,
                'start': period_start,
                'end': period_end,
                'invoice_date': invoice_date
                })
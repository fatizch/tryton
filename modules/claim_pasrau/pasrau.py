# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from trytond.pyson import Eval
from trytond.model import Unique
from trytond.pool import Pool
from trytond.server_context import ServerContext

from trytond.modules.coog_core import model, fields, coog_date, utils

__all__ = [
    'PartyCustomPasrauRate',
    'DefaultPasrauRate',
    'MoveLinePasrauRate',
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

RATE_ORIGIN = [
    ('default', 'Default'),
    ('manual', 'Manual')
    ]


class PartyCustomPasrauRate(model.CoogSQL, model.CoogView):
    'Party Custom Pasrau Rate'
    __name__ = 'party.pasrau.rate'

    effective_date = fields.Date('Effective date', required=True, select=True)
    pasrau_tax_rate = fields.Numeric('Pasrau tax rate', digits=(16, 4),
        required=True)
    origin = fields.Selection(RATE_ORIGIN, 'Origin')
    party = fields.Many2One('party.party', 'Party', required=True,
       ondelete='CASCADE', select=True)
    business_id = fields.Char('Business Id')

    @classmethod
    def __setup__(cls):
        super(PartyCustomPasrauRate, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('party_date_unique', Unique(t, t.party, t.effective_date),
                'The rate must be unique per party / date'),
            ]
        cls._error_messages.update({
                'no_party_found': 'No party found for NIR %(ssn)s '
                'and matricule %(matricule)s',
                'no_rate_found': 'No pasrau rate found for NIR %(ssn)s',
                })

    @classmethod
    def default_origin(cls):
        return 'manual'

    @classmethod
    def process_xml_file(cls, path):
        pool = Pool()
        Party = pool.get('party.party')
        errors = []
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
            effective_date = utils.today()
            for declaration in node_func(root_element, 'declaration'):
                for declaration_identification in node_func(declaration,
                        'declaration_identification'):
                    identifiant_metier = node_func(declaration_identification,
                        'identifiant_metier', True)

                for declaration_bilan in node_func(declaration,
                        'declaration_bilan'):
                    for salarie in node_func(declaration_bilan, 'salarie'):
                        ssn = node_func(salarie, 'NIR', True)
                        matricule = node_func(salarie, 'matricule', True)
                        party = []
                        if ssn:
                            party = Party.search([('ssn', 'like', ssn + '%')])
                        if not party and matricule:
                            party = Party.search([('code', '=', matricule)])
                        if not party:
                            errors.append(cls.raise_user_error(
                                    'no_party_found', {'ssn': ssn,
                                        'matricule': matricule},
                                    raise_exception=False))
                            continue
                        pasrau_tax_rate = node_func(salarie,
                            'taux_imposition_PAS', True)
                        if not pasrau_tax_rate:
                            errors.append(cls.raise_user_error('no_rate_found',
                                    {'ssn': ssn}, raise_exception=False))
                            continue
                        rate = party[0].update_pasrau_rate(effective_date,
                            Decimal(pasrau_tax_rate) / Decimal(100),
                            identifiant_metier)
                        if rate:
                            to_save.append(rate)
            if to_save:
                cls.save(to_save)
        return to_save, errors


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
        for key, prefixes in mapping.items():
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
                pasrau_dict = ServerContext().get('pasrau_data')
                if pasrau_dict:
                    pasrau_dict['pasrau_rate'] = candidate.rate
                    pasrau_dict['pasrau_rate_kind'] = 'default'
                    pasrau_dict['pasrau_rate_business_id'] = None
                    pasrau_dict['pasrau_rate_region'] = region
                    with ServerContext().set_context(pasrau_data=pasrau_dict):
                        return candidate.rate
                return candidate.rate
        cls.raise_user_error('no_default_pasrau', {
                'zip': zip_code,
                'income': '%.2f' % income,
                'start': period_start,
                'end': period_end,
                'invoice_date': invoice_date
                })


class MoveLinePasrauRate(model.CoogSQL, model.CoogView):
    'Move Line Pasrau Rate'

    __name__ = 'account.move.line.pasrau.rate'

    move_line = fields.Many2One('account.move.line', 'Move Line',
        ondelete='CASCADE', required=True, select=True)
    pasrau_rate = fields.Numeric('Rate', digits=(16, 4), required=True,
        select=True)
    pasrau_rate_kind = fields.Selection(RATE_ORIGIN, 'Pasrau Rate Kind')
    pasrau_rate_business_id = fields.Char('Pasrau Rate Business Id')
    pasrau_rate_region = fields.Char('Pasrau Rate Region')

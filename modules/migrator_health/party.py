# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.migrator import tools
from trytond.modules.coog_core import utils
from dateutil.relativedelta import relativedelta


__all__ = [
    'MigratorParty',
    ]


class MigratorParty(metaclass=PoolMeta):

    __name__ = 'migrator.party'

    @classmethod
    def __setup__(cls):
        super(MigratorParty, cls).__setup__()
        cls.columns.update({'hc_system': 'hc_system',
            'insurance_fund_number': 'insurance_fund_number'})
        cls.error_messages.update({
            'inexistent_insurance_fund_num': 'The insurance fund number %s'
            ' is inexistent in the data base',
            'inexistent_hc_system': 'The health care system %s'
            ' is inexistent in the data base',
            })

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorParty, cls).init_cache(rows, **kwargs)
        hc_system = [r['hc_system'] for r in rows if r['hc_system']]
        if hc_system:
            cls.cache_obj['h_care_system'] = tools.cache_from_search(
                'health.care_system',
                'code', ('code', 'in', hc_system))
        insurance_fund = [r['insurance_fund_number'] for r in rows
        if r.get('insurance_fund_number')]
        if insurance_fund:
            cls.cache_obj['health_care_system_number'] =\
                tools.cache_from_search('health.insurance_fund',
                    'code', ('code', 'in', insurance_fund))

    @classmethod
    def sanitize(cls, row, parent=None):
        row = super(MigratorParty, cls).sanitize(row)
        if (row['insurance_fund_number'] and
                len(row['insurance_fund_number']) < 9):
            row['insurance_fund_number'] = (row['hc_system'] +
                row['insurance_fund_number'][-3:] + '0000')
        return row

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        res = super(MigratorParty, cls).migrate_rows(
            rows, ids, **kwargs)
        cls.migrate_health_care_system(rows)
        return res

    @classmethod
    def check_existing_health_complement(cls, party_row, party):
        existing_health_complement = False
        for health_complement in party.health_complement:
            if (health_complement.hc_system.code == party_row['hc_system'].code
                and health_complement.insurance_fund_number ==
                    party_row['insurance_fund_number'].code):
                existing_health_complement = True
        if not existing_health_complement:
            for health_c in party.health_complement:
                if (health_c.hc_system.code == party_row['hc_system'].code
                        and health_c.insurance_fund_number !=
                        party_row['insurance_fund_number'].code):
                    health_c.insurance_fund_number = \
                        party_row['insurance_fund_number'].code
                    health_complement.save()
                    return True
                elif (health_c.hc_system.code != party_row['hc_system'].code
                        and health_c.insurance_fund_number !=
                            party_row['insurance_fund_number'].code):
                    health_c.date = utils.today() - relativedelta(days=1)
                    health_c.save()
                    return False
        return True

    @classmethod
    def migrate_health_care_system(cls, rows):
        pool = Pool()
        Party = pool.get(cls.model)
        HealthPartyComplement = pool.get('health.party_complement')
        health_complement_create = {}
        party_rows = list(rows)
        for party_row in party_rows:
            if party_row['hc_system'] and party_row['insurance_fund_number']:
                if party_row['hc_system'] in cls.cache_obj['h_care_system']:
                    if (party_row['insurance_fund_number']
                            in cls.cache_obj['health_care_system_number']):
                        cls.resolve_key(party_row, 'hc_system', 'h_care_system')
                        cls.resolve_key(party_row, 'insurance_fund_number',
                        'health_care_system_number')
                        cls.cache_obj['party'] = tools.cache_from_query(
                            'party_party', ('code', ),
                            ('code', [r['code'] for r in rows]))
                        party, = Party.search([('code', '=',
                            party_row['code'])])
                        # create health complement for first time
                        if party and not party.health_complement:
                            health_complement_create[party_row['code']] = {
                                'hc_system': party_row['hc_system'].id,
                                'insurance_fund_number':
                                party_row['insurance_fund_number'].code,
                                'party': cls.cache_obj['party'][
                                     party_row['code']],
                            }
                        # Check existing health_complement and update it
                        # if necessary or create a new one
                        else:
                            to_create_health_complement =\
                                cls.check_existing_health_complement(party_row,
                                    party)
                            if not to_create_health_complement:
                                health_complement_create[party_row['code']] = {
                                    'hc_system': party_row['hc_system'].id,
                                    'insurance_fund_number':
                                    party_row['insurance_fund_number'].code,
                                    'party': cls.cache_obj['party'][party_row[
                                        'code']],
                                    'date': utils.today(),
                                }
                    else:
                        cls.logger.error(cls.error_message(
                            'inexistent_insurance_fund_num') %
                            (party_row['code'],
                                party_row['insurance_fund_number']))
                else:
                    cls.logger.error(cls.error_message('inexistent_hc_system') %
                        (party_row['code'], party_row['hc_system']))
        if health_complement_create:
            HealthPartyComplement.create(
                list(health_complement_create.values()))

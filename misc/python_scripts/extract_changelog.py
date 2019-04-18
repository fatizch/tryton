#!/usr/bin/env python
# encoding: utf8

import os
import sys
from collections import defaultdict, OrderedDict

try:
    language = sys.argv[1]
except:
    sys.stderr.write('''
Usage :
    extract_chnagelog.py <language>
''')
    sys.exit()

conf = OrderedDict([
    ('Party management', ['party_cog', 'party_ssn', 'party_fr']),
    ('Contract management', ['contract_distribution', 'contract_group',
        'contract_insurance', 'contract_term_renewal', 'distribution_portfolio',
        'document_request_electronic_signature', 'offered', 'contract',
        'contract_identifiers', 'contract_insurance_health_fr',
        'contract_underwriting'
        ]),
    ('Contract Endorsement', ['endorsement_commission', 'endorsement',
        'endorsement_party', 'endorsement_premium', 'endorsement_process']),
    ('Claim', ['claim', 'claim_eligibility', 'claim_group_life_fr',
        'claim_indemnification', 'claim_indemnification_group', 'claim_life',
        'claim_pasrau', 'claim_prest_ij_service', 'claim_process',
        'claim_salary_fr', 'claim_group_life_fr', 'claim_insurer',
        'claim_reporting', 'dsn_standard', 'underwriting',
        'underwriting_claim']),
    ('Billing', ['account_invoice_cog', 'contract_instalment_plan',
        'contract_insurance_invoice', 'contract_insurance_invoice_dunning',
        ]),
    ('Payment', ['account_payment_cog', 'account_payment_sepa_cog']),
    ('Accounting', ['account_cog', 'account_per_product',
        'analytic_account_aggregate', 'analytic_coog', 'bank_fr',
        'account_invoice_slip']),
    ('Commission', ['analytic_commission', 'commission_insurance',
        'commission_insurance_prepayment', 'commission_insurance_recovery',
        'commission_insurer', 'insurer_reporting', 'commission_postponed']),
    ('Loan', ['loan']),
    ('Report Engine', ['report_engine']),
    ('Process', ['process_cog']),
    ('Rule Engine', ['rule_engine']),
    ('Transverse Functionnalities', ['event_log', 'event_log_party']),
    ('Technical/Core', ['coog_core', 'sequence_coog', 'migrator_claim',
        'migrator_contract_group', 'migrator']),
    ('Other', []),
    ('COOG API', []),
    ('COOG APP', []),
])

translation_fr = {
    'Party management': 'Gestion du référentiel tiers',
    'Contract management': 'Gestion contrat',
    'Contract Endorsement': 'Avenant Contrat',
    'Claim': 'Sinistre',
    'Billing': 'Cotisation',
    'Payment': 'Encaissement - Décaissement',
    'Accounting': 'Comptabilité',
    'Commission': 'Commission',
    'Loan': 'Emprunteur',
    'Process': 'Processus',
    'Report Engine': 'Editique',
    'Rule Engine': 'Moteur de règle',
    'Technical/Core': 'Noyau Technique',
    'Transverse Functionnalities': 'Fonctionnalités transerves',
    'Other': 'Autre',
    'COOG API': 'COOG API',
    'COOG APP': 'COOG APP',
}

version_report = defaultdict(str)

nb_version_functionnality = 0

module_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
    '..', '..', 'modules')


def treat_changelog(chapter, changelog, release_report):
    nb_functionnality = 0
    title_print = False
    for line in changelog.readlines():
        if not line.strip():
            continue
        if 'BUG' in line or 'OTH' in line:
            continue
        if 'Version ' in line:
            break
        if not title_print:
            print('')
            print('Module', module)
            title_print = True
        print(line[:-1])
        release_report[chapter] += '- ' + ' '.join(
            line[:-1].split(' ')[2:]) + '\n'
        nb_functionnality += 1
    return nb_functionnality

print('-------------Back Office Coog ----------------')
for module in sorted(os.listdir(module_dir)):
    if not os.path.isfile(os.path.join(module_dir, module, 'doc', language,
            'CHANGELOG')):
        print('')
        print('Module', module)
        print('   NO CHANGELOG FOUND')
        continue
    with open(os.path.join(module_dir, module, 'doc', language,
            'CHANGELOG'), 'r') as changelog:
        #  found chapter title
        chapter = ''
        for key, value in conf.items():
            if module in value:
                chapter = key
        if not chapter:
            chapter = 'Other'

        nb_version_functionnality += treat_changelog(chapter, changelog,
            version_report)

coog_api_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
    '..', '..', '..', 'api')
with open(os.path.join(coog_api_dir, 'doc', language, 'CHANGELOG'),
        'r') as changelog:
    print('\n------------- Coog API ----------------')
    nb_version_functionnality += treat_changelog('COOG API', changelog,
        version_report)

coog_app_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
    '..', '..', '..', 'coog-app')
with open(os.path.join(coog_app_dir, 'doc', language, 'CHANGELOG'),
        'r') as changelog:
    print('\n------------- Coog APP ----------------')
    nb_version_functionnality += treat_changelog('COOG APP', changelog,
        version_report)

print('\n\n----------%s New functionnalities------------------\n\n' %
    nb_version_functionnality)
print('\n\n----------Release note document------------------\n\n')

print('## COOG BACKEND\n' if language == 'en' else '## Back office COOG\n')

for key in list(conf.keys()):
    title = translation_fr[key] if language == 'fr' else key
    print('### %s' % title)
    print(version_report[key])

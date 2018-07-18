# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import datetime

from sql import Literal, Null
from sql.aggregate import Sum

from collections import defaultdict
from decimal import Decimal
from zipfile import ZipFile
from itertools import groupby
from lxml import etree
from io import BytesIO

from trytond.model import Unique
from trytond.config import config
from trytond.server_context import ServerContext
from trytond.pyson import Eval, Bool, Equal, Or, In
from trytond.transaction import Transaction
from trytond.model import Workflow, dualmethod, fields as tryton_fields
from trytond.pool import Pool, PoolMeta
from trytond.tools import memoize

from trytond.modules.coog_core import model, fields, utils, coog_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.process_cog.process import CoogProcessFramework

import gesti_templates

from benefit import EVENT_DESCS

LINE_KINDS = [
    ("ADO", "I.J. ADOPTION"),
    ("ARA", "Allocation maternite reduite pour adoption"),
    ("ARM", "Allocation forfaitaire repos maternel"),
    ("ASM", "I.J MALADIE MAJOREE + 6 MOIS"),
    ("ASN", "I.J MALADIE NORMALE + 6 MOIS"),
    ("AVP", "Alloc. accomp. fin de Vie cessa. act. temps Pl."),
    ("AVR", "Alloc. Accomp. fin de Vie cessation act. Red."),
    ("CAR", "CARENCE"),
    ("CIJ", "COMPLEMENT IJ > PLAFOND -CRPCEN-"),
    ("CIN", "CONSTAT D'INDU"),
    ("CUM", "I.J.MAJOREES CURE"),
    ("CUN", "I.J. NORMALES CURE"),
    ("CUR", "I.J.REDUITES CURE (RENTE)"),
    ("EEN", "ALLOCATION EXPOSITION ARRET + 6 MOIS ET 3 ENFANTS"),
    ("EME", "ALLOCATION EXPOSITION MAJOREE 3 ENFANTS"),
    ("EMN", "ALLOCATION EXPOSITION ARRET + 6 MOIS"),
    ("ENO", "ALLOCATION EXPOSITION NORMALE"),
    ("IJMAJ", "I.J. MAJOREES"),
    ("IJNOR", "I.J. NORMALES"),
    ("IPA", "INDEMNITE PATERNITE PAMC"),
    ("IPC", "INDEMNITE PATERNITE CONJOINT PAMC"),
    ("IPD", "FORF.24H>DUREE>12"),
    ("IPI", "INDEMNITE PATERNITE CONJOINT INFIRMIER"),
    ("IPS", "PERTE DE SALAIRE"),
    ("IRA", "INDEM.REMPL.MATER REDUITE(ADOPTION)"),
    ("IRC", "INDEM. DE REMPL.CJTES.COLLABORATRICES"),
    ("IRG", "MAJOR.INDEM.REMPL.MATER(A.GEMELL.)"),
    ("IRM", "INDEMN.REMPLACEMENT MATER NORMALE"),
    ("IRP", "MAJOR.INDEM.REMPL.MATER(ET PATHOL)"),
    ("ISM", "IJ SUPPLEMENTAIRE MATERNITE"),
    ("ITI", "INDEMNITE TEMPORAIRE D'INAPTITUDE"),
    ("MIJ", "I.J. MINIMUM  MAJOREE"),
    ("MIN", "I.J. MINIMUM  NORMALE"),
    ("MIT", "I.J. MI-TEMPS"),
    ("NEN", "ALLOCATION NUIT MAJOREE ARRET + 6 MOIS ET 3 ENFANTS"),
    ("NME", "ALLOCATION NUIT MAJOREE  3 ENFANTS"),
    ("NMN", "ALLOCATION NUIT MAJOREE ARRET + 6 MOIS"),
    ("NNO", "ALLOCATION NUIT NORMALE"),
    ("PER", "I.J. PATERNITE"),
    ("POS", "I.J. POSNATALES"),
    ("PRE", "I.J. PRENATALES"),
    ("REGRCJ", "REGULARISATION REGUL.CONTRIB. SOCIALE GENERALISEE"),
    ("REGRRD", "REGULARISATION REGUL. REMBOURSEMENT DETTE SOCIALE"),
    ("REN", "I.J. REDUITES POUR RENTE"),
    ("RETCRD", "RETENUE R.D.S."),
    ("RETCSJ", "RETENUE C.S.G."),
    ("RETRCJ", "RETENUE REGUL.CONTRIB. SOCIALE GENERALISEE"),
    ("RETRRD", "RETENUE REGUL. REMBOURSEMENT DETTE SOCIALE"),
    ("RPR", "RECUPERATION INDU"),
    ]

TAXES_KINDS = {'REGRCJ', 'REGRRD', 'RETCRD', 'RETCSJ', 'RETRCJ', 'RETRRD'}

INDEMN_KINDS = {x[0] for x in LINE_KINDS} - TAXES_KINDS

AUTOMATIC_KINDS = {'CAR', 'IJMAJ', 'IJNOR'}

BPIJ_NS = '{www.cnamts.fr/tlsemp/IJ}'


__all__ = [
    'ClaimIjSubscriptionRequestGroup',
    'ClaimIjSubscriptionRequest',
    'ClaimIjSubscription',
    'ClaimService',
    'ClaimIndemnification',
    'ClaimIjPeriod',
    'ClaimIjPeriodLine',
    ]


SUBSCRIPTION_STATES = [
    ('undeclared', 'Undeclared'),
    ('declared', 'Declared'),
    ('in_error', 'In Error'),
    ('declaration_confirmed', 'Declaration Confirmed'),
    ('deleted', 'Deleted'),
    ('deletion_confirmed', 'Deletion Confirmed'),
    ]

SUBSCRIPTION_REQUEST_STATES = [
    ('unprocessed', 'Unprocessed'),
    ('processing', 'Processing'),
    ('failed', 'Failed'),
    ('confirmed', 'Confirmed'),  # CR is ok
    ]

SUBSCRIPTION_REQUEST_GROUP_STATES = [
    ('processing', 'Processing'),
    ('failed', 'Failed'),
    ('acknowledged', 'Acknowledged'),  # ARL (accuse de reception logique) ok
    ]


class ClaimIjSubscriptionRequestGroup(Workflow, model.CoogSQL, model.CoogView):
    'Claim IJ Subscription Request Group'
    __name__ = 'claim.ij.subscription_request.group'

    _rec_name = 'identification'

    state = fields.Selection(SUBSCRIPTION_REQUEST_GROUP_STATES, 'State',
        required=True, readonly=True, select=True)
    requests = fields.One2Many('claim.ij.subscription_request', 'group',
        'Requests', readonly=True, target_not_required=True)
    identification = fields.Char('Identification', readonly=True,
        required=True)
    return_date = fields.Date('Return Date', readonly=True,
        states={
            'required': Eval('state').in_(['failed', 'acknowledged']),
            },
        depends=['state'])
    error_code = fields.Char('Error Code', readonly=True,
        states={
            'invisible': (~Eval('error_code') & (Eval('state') != 'failed')),
            },
        depends=['state'])
    error_message = fields.Text('Error Message', readonly=True,
        states={
            'invisible': (~Eval('error_message') & (Eval('state') != 'failed')),
            },
        depends=['state'])

    @classmethod
    def __setup__(cls):
        super(ClaimIjSubscriptionRequestGroup, cls).__setup__()
        cls._transitions |= set((
                ('processing', 'acknowledged'),
                ('processing', 'failed'),
                ))
        t = cls.__table__()
        cls._sql_constraints += [('unique_identification',
                Unique(t, t.identification),
                'The identification must be unique')]

    @classmethod
    def default_state(cls):
        return 'processing'

    @classmethod
    @Workflow.transition('failed')
    def fail_transition(cls, groups, cause, label):
        all_requests = sum([list(x.requests) for x in groups], [])
        Pool().get('claim.ij.subscription_request').fail(all_requests, cause,
            label)
        cls.write(groups, {'error_code': cause, 'error_message': label,
                'return_date': utils.today()})

    @classmethod
    @Workflow.transition('acknowledged')
    def acknowledge_transition(cls, groups):
        # This only means that the ARL is ok for the groups
        all_requests = sum([list(x.requests) for x in groups], [])
        Pool().get('event').notify_events(all_requests,
            'prest_ij_request_arl_ok')
        cls.write(groups, {'return_date': utils.today()})

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if not values.get('identification'):
                values['identification'] = cls.generate_identification()
            if values.get('identification') == '':
                values['identification'] = None
        return super(ClaimIjSubscriptionRequestGroup, cls).create(vlist)

    @classmethod
    def generate_identification(cls, kind='group'):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        ClaimConfiguration = pool.get('claim.configuration')
        claim_config = ClaimConfiguration.get_singleton()
        assert kind in ('period', 'group'), 'Unknown kind %s' % kind
        if kind == 'period':
            sequence = claim_config.prest_ij_period_sequence
        else:
            sequence = claim_config.prest_ij_sequence
        assert sequence
        return Sequence.get_id(sequence.id)

    @property
    def _identification(self):
        assert self.identification
        return self.identification

    def get_prefixed_id(self, prefix):
        return prefix + self._identification

    @classmethod
    def get_unprefixed_id(cls, file_id, kind):
        prefix = cls.get_prefix(kind)
        return file_id[len(prefix):]

    @classmethod
    def get_prefix(cls, kind):
        code_ga = cls.get_ij_conf_item('code_ga')
        if kind == 'header':
            return code_ga + '-E'
        elif kind == 'document':
            return code_ga + '-D'

    def generate_header_xml(self, common_data):
        header = gesti_templates.GestipHeader(common_data)
        return str(header)

    def generate_document_xml(self, common_data):
        doc = gesti_templates.GestipDocument(common_data)
        return str(doc)

    def get_timestamp(self, n):
        return n.strftime('%Y-%m-%dT%H:%M:%SZ')

    def get_filename_timestamp(self, n):
        return n.strftime('%Y%m%d%H%M%S%f')[:-3]

    @classmethod
    @memoize(10)
    def get_ij_conf_item(cls, key):
        item = config.get('prest_ij', key)
        assert item, '%s not set in prest_ij section of configuration' % key
        return item

    def generate_files(self, output_dir):
        n = datetime.datetime.utcnow()
        timestamp = self.get_timestamp(n)
        filename_timestamp = self.get_filename_timestamp(n)

        code_ga = self.get_ij_conf_item('code_ga')
        siret_opedi = self.get_ij_conf_item('siret_opedi')
        access_key = self.get_ij_conf_item('access_key')
        opedi_name = self.get_ij_conf_item('opedi_name')

        header_filename = '-'.join(['E-ENTGESTIP', code_ga +
            filename_timestamp]) + '.xml'
        gesti_document_filename = '-'.join(['D-GESTIP', code_ga +
            filename_timestamp]) + '.xml'

        common_data = {
            'timestamp': timestamp,
            'siret_opedi': siret_opedi,
            'gesti_header_identification': self.get_prefixed_id(
                self.get_prefix('header')),
            'gesti_document_identification': self.get_prefixed_id(
                self.get_prefix('document')),
            'header_filename': header_filename,
            'gesti_document_filename': gesti_document_filename,
            'access_key': access_key,
            'code_ga': code_ga,
            'opedi_name': opedi_name,
            'requests': self.requests,
            }

        header_data = self.generate_header_xml(common_data)
        doc_data = self.generate_document_xml(common_data)

        archive_name = os.path.join(os.path.abspath(output_dir),
            self._identification + '.zip')
        with ZipFile(archive_name, 'w') as archive:
                archive.writestr(header_filename, header_data)
                archive.writestr(gesti_document_filename, doc_data)

    @dualmethod
    def process(cls, groups, output_dir):
        for group in groups:
            group.generate_files(output_dir)

    @classmethod
    def get_file_kind(cls, data):
        f = BytesIO(data)
        mapping = {
            'ARLGESTIP': 'arl_data',
            'CRGESTIP': 'cr_data',
            'IJ': 'bpij_data',
            'ENTARLGESTIP': 'arl_header',
            'ENTCRGESTIP': 'cr_header',
            'ENTBPIJ': 'bpij_header',
            }
        for event, element in etree.iterparse(f):
            return mapping[element.nsmap[None].split(':')[-1]]

    @classmethod
    def process_arl_data(cls, data):
        doc = etree.fromstring(data)
        ns_arg = {'n': 'urn:cnamts:tlsemp:ARLGESTIP'}
        header_id = doc.xpath("//n:DiagEntete/n:Identification/text()",
                namespaces=ns_arg)[0]
        header_state = doc.xpath("//n:DiagEntete/n:Diagnostic/n:Etat/text()",
            namespaces=ns_arg)[0]
        if header_state == 'R':
            header_reject_cause = doc.xpath(
                "//n:DiagEntete/n:Diagnostic/n:Cause/text()",
                namespaces=ns_arg)
            if header_reject_cause:
                header_reject_cause = header_reject_cause[0]
            else:
                header_reject_cause = None
            header_reject_label = doc.xpath(
                "//n:DiagEntete/n:Diagnostic/n:Libelle/text()",
                namespaces=ns_arg)[0]
            cls.fail_transition(cls.search_from_file_identification(
                header_id, 'header'), header_reject_cause, header_reject_label)
        else:
            doc_diags = doc.xpath("//n:DiagEntete/n:DiagDocument",
                    namespaces=ns_arg)
            for doc_diag in doc_diags:
                doc_id = doc_diag.xpath('n:Mindex/n:Identification/text()',
                        namespaces=ns_arg)[0]
                doc_state = doc_diag.xpath('n:Diagnostic/n:Etat/text()',
                        namespaces=ns_arg)[0]
                groups = cls.search_from_file_identification(doc_id, 'document')
                if doc_state == 'R':
                    doc_reject_cause = doc_diag.xpath(
                        'n:Diagnostic/n:Cause/text()', namespaces=ns_arg)[0]
                    doc_reject_label = doc_diag.xpath(
                        'n:Diagnostic/n:Libelle/text()', namespaces=ns_arg)[0]
                    cls.fail_transition(groups, doc_reject_cause,
                        doc_reject_label)
                else:
                    cls.acknowledge_transition(groups)

    @classmethod
    def process_cr_data(cls, data):
        Request = Pool().get('claim.ij.subscription_request')
        doc = etree.fromstring(data)
        ns_arg = {'n': 'urn:cnamts:tlsemp:CRGESTIP'}
        doc_id = doc.xpath("//n:DiagDocument/n:Mindex/n:Identification/text()",
                namespaces=ns_arg)[0]
        group = cls.search_from_file_identification(doc_id, 'document')
        group = group[0]
        diags = doc.xpath("//n:DiagDocument/n:Diagnostic",
            namespaces=ns_arg)
        for diag in diags:
            siren = cls.get_siren_from_diag_element(diag, ns_arg)
            ssn = cls.get_ssn_from_diag_element(diag, ns_arg)
            requests = group.get_requests_from_diagnostic_data(siren,
                ssn)
            assert requests, 'No requests found for diagnostic element %s' \
                ' in document %s' % (
                    etree.tostring(diag, pretty_print=True, encoding='utf8'),
                    doc_id)
            op_state = diag.xpath('n:Etat/text()', namespaces=ns_arg)[0]
            if op_state == 'R':
                op_reject_cause = diag.xpath('n:Cause/text()',
                        namespaces=ns_arg)[0]
                op_reject_label = diag.xpath('n:Libelle/text()',
                        namespaces=ns_arg)[0]
                Request.fail(requests, cause=op_reject_cause,
                    label=op_reject_label)
            else:
                Request.acknowledge(requests)

    @classmethod
    def search_from_file_identification(cls, identification, kind):
        search_id = cls.get_unprefixed_id(identification, kind)
        res = cls.search([('identification', '=', search_id)])
        assert res, 'No IJ request group found with id %s' % identification
        return res

    @staticmethod
    def get_siren_from_diag_element(diag, ns_arg):
        siren = diag.xpath('n:Entreprise/n:Identite/text()',
                namespaces=ns_arg)
        assert siren, 'No identity for diagnostic element %s' \
            % etree.tostring(diag, pretty_print=True,
                encoding='utf8')
        siren = siren[0]
        return siren

    @staticmethod
    def get_ssn_from_diag_element(diag, ns_arg):
        nir = diag.xpath(
            'n:Entreprise/n:Salarie/n:NIR/text()',
            namespaces=ns_arg)
        if not nir:
            return None
        assert len(nir) == 1
        return nir[0]

    def get_requests_from_diagnostic_data(self, siren, ssn):
        def match(x):
            return (x.subscription.siren == siren) and (
                (not ssn) or (x.ssn and x.ssn[:-2] == ssn))
        return [x for x in self.requests if match(x)]


class ClaimIjSubscriptionRequest(Workflow, model.CoogSQL, model.CoogView):
    'Claim IJ Subscription Request'

    __name__ = 'claim.ij.subscription_request'

    date = fields.Date('Date', readonly=True, required=True)
    period_start = fields.Date('Period Start', readonly=True, states={
            'invisible': ~Eval('ssn'),
            'required': Bool(Eval('ssn') & Equal(Eval('operation'), 'cre')),
            }, depends=['ssn', 'operation'])
    period_end = fields.Date('Period End', readonly=True, states={
            'invisible': ~Eval('ssn')
            }, depends=['ssn', 'operation'])
    retro_date = fields.Date('Retroactive Date', readonly=True, states={
            'invisible': ~Eval('ssn'),
            'required': Bool(Eval('ssn') & Equal(Eval('operation'), 'cre')),
            }, depends=['ssn', 'operation'])
    period_identification = fields.Char('Period Identification', readonly=True,
        states={
            'invisible': ~Eval('ssn'),
            'required': Bool(Eval('ssn')) & Bool(Eval('operation') == 'cre'),
            }, depends=['ssn', 'operation'])
    state = fields.Selection(SUBSCRIPTION_REQUEST_STATES, 'State',
        required=True, readonly=True, select=True)
    operation = fields.Selection([('cre', 'CRE'), ('sup', 'SUP')],
        'Operation', readonly=True)
    subscription = fields.Many2One('claim.ij.subscription', 'Subscription',
        required=True, readonly=True, ondelete='RESTRICT', select=True)
    siren = fields.Function(
        fields.Char('Siren'),
        'on_change_with_siren')
    ssn = fields.Function(
        fields.Char('SSN'),
        'on_change_with_ssn')
    party = fields.Function(
        fields.Many2One('party.party', 'Party', states={
            'invisible': ~Eval('ssn'),
            }, depends=['ssn']),
        'on_change_with_party')
    group = fields.Many2One('claim.ij.subscription_request.group', 'Group',
        readonly=True, ondelete='RESTRICT', select=True,
        states={
            'required': Eval('state').in_(
                ['processing', 'failed', 'acknowledged']),
            },
        depends=['state'])
    error_code = fields.Char('Error Code', readonly=True,
        states={
            'invisible': (~Eval('error_code') & (Eval('state') != 'failed')),
            },
        depends=['state'])
    error_message = fields.Text('Error Message', readonly=True,
        states={
            'invisible': (~Eval('error_message') & (Eval('state') != 'failed')),
            },
        depends=['state'])
    method = fields.Selection([
            ('manual', 'Manual'),
            ('automatic', 'Automatic')],
        'Method', required=True, readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(ClaimIjSubscriptionRequest, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [('unique_period_identification',
                Unique(t, t.period_identification),
                'The period identification must be unique')]
        cls._transitions |= set((
                ('unprocessed', 'processing'),
                ('processing', 'failed'),
                ('processing', 'confirmed'),
                ))

    @classmethod
    def default_state(cls):
        return 'unprocessed'

    @classmethod
    def default_method(cls):
        return 'automatic'

    @fields.depends('subscription')
    def on_change_with_siren(self, name=None):
        return self.subscription.siren if self.subscription else ''

    @fields.depends('subscription')
    def on_change_with_ssn(self, name=None):
        return self.subscription.ssn if self.subscription else ''

    @fields.depends('subscription')
    def on_change_with_party(self, name=None):
        return self.subscription.party.id \
            if self.subscription and self.subscription.party else ''

    def get_rec_name(self, name):
        return self.operation.upper() if self.operation else self.id

    @classmethod
    @Workflow.transition('failed')
    def fail(cls, requests, cause='', label=''):
        cls.write(requests, {'error_code': cause, 'error_message': label})
        cls.update_subscriptions(requests, 'failed')
        Pool().get('event').notify_events(requests, 'prest_ij_request_failed',
            description=label or cause)

    @classmethod
    @Workflow.transition('confirmed')
    def acknowledge(cls, requests):
        cls.update_subscriptions(requests, 'confirmed')
        Pool().get('event').notify_events(requests,
            'prest_ij_request_acknowledged')

    @classmethod
    def update_subscriptions(cls, requests, new_request_state):
        Subscription = Pool().get('claim.ij.subscription')
        if new_request_state == 'failed':
            Subscription.write([x.subscription for x in requests],
                {'state': 'in_error'})
        else:
            cre_subs, sup_subs = [], []
            [cre_subs.append(x.subscription) if x.operation == 'cre'
                else sup_subs.append(x.subscription) for x in requests]
            mapping = {
                'processing':
                {'cre': 'declared', 'sup': 'deleted'},
                'confirmed':
                {'cre': 'declaration_confirmed', 'sup': 'deletion_confirmed'}
                }
            if cre_subs:
                Subscription.write(cre_subs,
                    {'state': mapping[new_request_state]['cre']})
            if sup_subs:
                Subscription.write(sup_subs,
                    {'state': mapping[new_request_state]['sup']})

    @classmethod
    @Workflow.transition('processing')
    def process(cls, requests, output_dir):
        pool = Pool()
        Group = pool.get('claim.ij.subscription_request.group')
        if requests:
            group = Group()
            group.save()
            cls.write(requests, {
                    'group': group.id,
                    })
            group.process(output_dir)
            group.save()
            cls.update_subscriptions(requests, 'processing')
            pool.get('event').notify_events(requests, 'prest_ij_request_sent')
            return group


class ClaimIjSubscription(CoogProcessFramework, model.CoogView):
    'Claim IJ Subscription'

    __name__ = 'claim.ij.subscription'

    parties = fields.Function(
        fields.Many2Many('party.party', None, None, 'Parties', states={
            'invisible': Bool(Eval('ssn')),
            }, depends=['ssn']),
        'getter_parties')
    party = fields.Function(
        fields.Many2One('party.party', 'Party', states={
            'invisible': ~Eval('ssn'),
            }, depends=['ssn']),
        'getter_party')
    siren = fields.Char('Siren', readonly=True, required=True)
    ssn = fields.Char('SSN', readonly=True,
        states={
            'invisible': ~Eval('ssn'),
            'required': Bool(Eval('ssn')),
            }, depends=['ssn'])
    state = fields.Selection(SUBSCRIPTION_STATES, 'State', readonly=True)
    error_code = fields.Function(
        fields.Char('Error Code'),
        'on_change_with_error_code')
    date = fields.Function(fields.Date(
            'Declaration Or Deletion Date', readonly=True),
        loader='on_change_with_date')
    confirmation_date = fields.Function(fields.Date(
            'Confirmation Date', readonly=True),
        loader='on_change_with_confirmation_date')
    requests = fields.One2Many('claim.ij.subscription_request', 'subscription',
        'Requests', readonly=True, delete_missing=True,
        order=[('date', 'DESC'), ('id', 'DESC')])
    requests_event_logs = fields.Function(
        fields.Many2Many('event.log', None, None, 'Requests Event Logs'),
        'get_requests_event_logs')
    activated = fields.Boolean('Activated', readonly=True)
    ij_activation = fields.Function(fields.Boolean('IJ Activation', states={
                'readonly': Bool(Eval('activated')),
                'invisible': Bool(Eval('ssn')),
                }, depends=['activated', 'ssn']),
        'on_change_with_ij_activation', setter='setter_ij_activation')
    method = fields.Function(
        fields.Selection([
            ('manual', 'Manual'),
            ('automatic', 'Automatic')], 'Method',
            states={
                'invisible': Or(~Eval('ssn'), ~Eval('requests')),
                'required': Bool(Eval('ssn')),
                }, depends=['ssn', 'requests']),
        'getter_method')
    subscriber = fields.Function(
        fields.Many2One('party.party', 'Subscriber', required=True),
        'getter_subscriber')
    periods_to_treat = fields.One2ManyDomain('claim.ij.period', 'subscription',
        'Periods to Treat', domain=[('state', '!=', 'treated')], readonly=True,
        delete_missing=True, states={'invisible': ~Eval('periods_to_treat')})
    claims = fields.Function(
        fields.Many2Many('claim', None, None, 'Claims',
            states={'invisible': ~Eval('claims')}),
        'getter_claims')

    @classmethod
    def __setup__(cls):
        super(ClaimIjSubscription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [('unique_subscription',
                Unique(t, t.siren, t.ssn), 'There must be only one IJ '
                'subscription per siren / ssn')]
        cls._buttons.update({
                'button_relaunch_process': {
                    'readonly': (Eval('state') != 'in_error')},
                'button_create_ij_subscription_request': {
                    'invisible': ~Eval('ssn') | ~In(Eval('state'),
                        ['undeclared', 'deletion_confirmed'])},
                'button_start_period_treatment': {},
                })
        cls._error_messages.update({
                'periods_must_be_treated': '%(number)s periods must be '
                'treated before going on',
                })

    @classmethod
    @model.ModelView.button_action(
        'claim_prest_ij_service.act_manual_ij_subscription_request')
    def button_create_ij_subscription_request(cls, instances):
        pass

    @classmethod
    def default_siren(cls):
        active_id = Transaction().context.get('active_id')
        if active_id:
            return Pool().get('party.party')(active_id).siren

    @classmethod
    def default_ssn(cls):
        active_id = Transaction().context.get('active_id')
        if active_id:
            return Pool().get('party.party')(active_id).ssn

    @classmethod
    def default_state(cls):
        return 'undeclared'

    def get_rec_name(self, name):
        return self.parties[0].rec_name

    def getter_claims(self, name):
        return [x.claim.id for x in self.periods_to_treat if x.claim]

    def getter_method(self, name):
        requests = self.requests
        return requests[0].method if requests else 'automatic'

    def getter_parties(self, name):
        if not self.siren and not self.ssn:
            return []
        search_field = 'ssn' if self.ssn else 'siren'
        return sorted([x.id for x in Pool().get('party.party').search(
                    [(search_field, '=', getattr(self, search_field))])])

    @classmethod
    def getter_subscriber(cls, subscriptions, name):
        Party = Pool().get('party.party')
        matches = {}
        sirens = []

        for subscription in subscriptions:
            matches[subscription.siren] = subscription.id
            sirens.append(subscription.siren)

        parties = Party.search([('siren', 'in', sirens)])

        subscriptions = {}
        for party in parties:
            subscriptions[matches[party.siren]] = party.id

        return subscriptions

    def getter_party(self, name):
        if self.parties:
            return self.parties[0].id

    def get_requests_event_logs(self, name):
        EventLog = Pool().get('event.log')
        return [x.id for x in EventLog.search([
                ('object_', 'in', [str(x) for x in self.requests])])]

    @fields.depends('requests', 'state')
    def on_change_with_error_code(self, name=None):
        if self.state != 'in_error':
            return ''
        requests = [x for x in self.requests if x.state == 'failed']
        if requests:
            return requests[0].error_code

    @fields.depends('requests')
    def on_change_with_date(self, name=None):
        requests = [x for x in self.requests if x.state not in ['unprocessed']]
        if requests:
            return requests[0].date

    @fields.depends('requests')
    def on_change_with_confirmation_date(self, name=None):
        requests = [x for x in self.requests
            if x.state == 'confirmed']
        if requests:
            return requests[0].group.return_date

    @fields.depends('activated')
    def on_change_with_ij_activation(self, name=None):
        return self.activated

    @classmethod
    def setter_ij_activation(cls, instances, name, value):
        cls.write(instances, {'activated': value})

    @classmethod
    def create_subscription_requests(cls, objects, operation, date,
            kind):
        to_create = []
        pool = Pool()
        Request = pool.get('claim.ij.subscription_request')
        Group = pool.get('claim.ij.subscription_request.group')
        Subscription = pool.get('claim.ij.subscription')
        if kind == 'company':
            for sub in objects:
                to_create.append({
                        'date': date,
                        'subscription': sub,
                        'operation': operation,
                        })
        elif kind == 'person':
            if operation == 'sup':
                subscriptions = Subscription.browse(objects)
                for subscription in subscriptions:
                    values = {
                        'date': date,
                        'subscription': subscription,
                        'operation': operation,
                        'period_start': None,
                        'retro_date': None,
                        'period_end': None,
                        }
                    to_create.append(values)
            else:
                for key, services in groupby(objects, key=lambda x: (
                            x.loss.covered_person, x.contract.subscriber)):
                    services = list(services)
                    covered, subscriber = key
                    sub, = Pool().get('claim.ij.subscription').search([
                            ('ssn', '=', covered.ssn),
                            ('siren', '=', subscriber.siren),
                            ])
                    min_start_date = min(
                        [x.prest_ij_start_date() for x in services])
                    max_end_date = max(
                        [(x.prest_ij_end_date() or datetime.date.min)
                            for x in services])
                    if (min_start_date < date):
                        values = {
                            'date': date,
                            'subscription': sub,
                            'operation': operation,
                            'period_start': min_start_date,
                            'retro_date': min_start_date,
                            'period_end': max_end_date
                            if max_end_date != datetime.date.min else None,
                            }
                        if operation == 'cre':
                            values['period_identification'] = \
                                Group.generate_identification(kind='period')
                        to_create.append(values)

        if to_create:
            return Request.create(to_create)

    @classmethod
    @model.CoogView.button_action(
        'claim_prest_ij_service.act_relaunch_ij_subscription')
    def button_relaunch_process(cls, subscriptions):
        pass

    @classmethod
    @model.CoogView.button_action(
        'claim_prest_ij_service.act_start_period_treatment')
    def button_start_period_treatment(cls, subscriptions):
        pass

    @classmethod
    def end_process(cls, instances):
        for instance in instances:
            if instance.periods_to_treat:
                cls.append_functional_error('periods_must_be_treated',
                    {'number': str(len(instance.periods_to_treat))})

    @classmethod
    def finalize_add_periods(cls, instances):
        process, = Pool().get('process').process_from_kind(
            'prest_ij_treatment') or [None]
        if process and instances:
            cls.write(instances,
                {'current_state': process.first_step()})


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def prest_ij_start_date(self):
        return self.loss.start_date

    def prest_ij_end_date(self):
        return None

    def prest_ij_retro_start_date(self):
        return None


class ClaimIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    prestij_periods = fields.One2Many('claim.ij.period', 'indemnification',
        'PrestIJ Periods', delete_missing=False, target_not_required=True,
        readonly=True)
    has_prestij_periods = fields.Function(
        fields.Boolean('Has PrestIJ Periods'),
        'getter_has_prestij_periods')

    @classmethod
    def delete(cls, indemnifications):
        Period = Pool().get('claim.ij.period')
        periods = Period.search([('indemnification', 'in', indemnifications)])
        deleted = ServerContext().get('deleted_prestij_periods', None)
        Period.write(periods, {'indemnification': None})
        if deleted is not None:
            deleted += periods
        super(ClaimIndemnification, cls).delete(indemnifications)

    def getter_has_prestij_periods(self, name):
        return bool(self.prestij_periods)


class ClaimIjPeriod(model.CoogSQL, model.CoogView, ModelCurrency):
    'Claim Ij Period'

    __name__ = 'claim.ij.period'

    subscription = fields.Many2One('claim.ij.subscription', 'subscription',
        required=True, select=True, ondelete='CASCADE', readonly=True,
        domain=[('ssn', '!=', None)])
    lines = fields.One2Many('claim.ij.period.line', 'period', 'Lines',
        delete_missing=True, readonly=True)
    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification', ondelete='RESTRICT', select=True, readonly=True,
        states={'invisible': ~Eval('indemnification')})
    reception_date = fields.DateTime('Reception Date', required=True,
        readonly=True)
    sign = fields.Selection([('payment', 'Payment'),
            ('cancellation', 'Cancellation')], 'Sign', readonly=True)
    period_kind = fields.Selection(EVENT_DESCS, 'Kind', readonly=True)
    accounting_date = fields.Date('Accounting Date', required=True,
        readonly=True)
    start_date = fields.Date('Start Date', required=True, readonly=True)
    # The "required" on end_date is not in the specification, but we do not
    # handle this case for now
    end_date = fields.Date('End Date', required=True, domain=[
            ('end_date', '>=', Eval('start_date'))], depends=['start_date'],
        readonly=True)
    beneficiary_kind = fields.Selection([
            ('party', 'Party'), ('company', 'Company')], 'Beneficiary Kind',
        readonly=True)
    state = fields.Selection([
            ('received', 'Received'), ('treated', 'Treated')], 'State',
        readonly=True)
    automatic_action = fields.Function(
        fields.Selection([
                ('manually_treated', 'Manually Treated'),
                ('treated', 'Treated'),
                ('missing_claim', 'Missing Claim'),
                ('cancel_period', 'Cancel period'),
                ('cancelled_non_paid_period', 'Cancelled (non-paid) period'),
                ('cancellation_non_paid', 'Cancellation of (non-paid) period'),
                ('new_period', 'New Period'),
                ('waiting_previous_period', 'Waiting Previous Period'),
                ('no_automatic', 'Cannot determine course of action')],
            'Automatic Action'),
        'getter_automatic_action')
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        'getter_party', searcher='search_party')
    subscriber = fields.Function(
        fields.Many2One('party.party', 'Subscriber'),
        'getter_subscriber')
    service = fields.Function(
        fields.Many2One('claim.service', 'Service'),
        'getter_service')
    claim = fields.Function(
        fields.Many2One('claim', 'Claim'),
        'getter_claim')
    number_of_days = fields.Function(
        fields.Integer('Number of days'),
        'getter_number_of_days')
    indemnification_amount = fields.Function(
        fields.Numeric('Indemnification Amount', digits=(16, 2)),
        'getter_amount')
    taxes_amount = fields.Function(
        fields.Numeric('Taxes Amount', digits=(16, 2)),
        'getter_amount')
    total_amount = fields.Function(
        fields.Numeric('Total Amount', digits=(16, 2)),
        'getter_total_amount')
    other_periods = fields.Function(
        fields.Many2Many('claim.ij.period', None, None, 'Other Periods',
            states={'invisible': ~Eval('other_periods')}),
        'getter_other_periods')
    same_periods = fields.Function(
        fields.Many2Many('claim.ij.period', None, None, 'Same Periods'),
        'getter_same_periods')
    main_kind = fields.Function(
        fields.Selection(LINE_KINDS, 'Main Kind'),
        'getter_main_kind')
    total_per_day_amount = fields.Function(
        fields.Numeric('Total per day Amount', digits=(16, 2)),
        'getter_amount')
    indemnification_beneficiary = fields.Function(
        fields.Many2One('party.party', 'Beneficiary'),
        'getter_indemnification')
    indemnification_status = fields.Function(
        fields.Selection('selector_indemnification_status',
            'Indemnification Status'),
        'getter_indemnification')
    indemnification_total_amount = fields.Function(
        fields.Numeric('Indemnification Total Amount', digits=(16, 2)),
        'getter_indemnification')

    @classmethod
    def __setup__(cls):
        super(ClaimIjPeriod, cls).__setup__()
        cls._order = [('id', 'DESC'), ('start_date', 'DESC'),
            ('sign', 'DESC')]

    @classmethod
    def default_state(cls):
        return 'received'

    @classmethod
    def write(cls, *args):
        for data in args[1::2]:
            if 'indemnification' not in data:
                continue
            data['state'] = 'treated' if data['indemnification'] else \
                'received'
        super(ClaimIjPeriod, cls).write(*args)

    @classmethod
    def getter_amount(cls, periods, name):
        line = Pool().get('claim.ij.period.line').__table__()
        cursor = Transaction().connection.cursor()

        column = Sum(line.total_amount)
        if name == 'indemnification_amount':
            targets = list(INDEMN_KINDS)
        elif name == 'total_per_day_amount':
            targets = list(INDEMN_KINDS)
            column = Sum(line.amount)
        elif name == 'taxes_amount':
            targets = list(TAXES_KINDS)
        else:
            raise Exception('Unhandled name %s' % name)

        values = {x.id: Decimal(0) for x in periods}

        cursor.execute(*line.select(
                line.period, column,
                where=line.period.in_([x.id for x in periods])
                & line.kind.in_(targets),
                group_by=[line.period]))

        values.update(dict(cursor.fetchall()))

        return values

    def getter_automatic_action(self, name):
        if not self.claim:
            return 'missing_claim'
        if self.state == 'treated':
            if not self.indemnification:
                # Automatic treatment will set the indemnification field
                return 'manually_treated'
            else:
                return 'treated'
        if self.main_kind not in TAXES_KINDS | AUTOMATIC_KINDS:
            return 'no_automatic'
        if not self.other_periods:
            # No other period for this subscription
            return 'new_period' if self.sign == 'payment' else 'cancel_period'
        if not self.same_periods:
            # I'm alone for those dates
            return 'new_period' if self.sign == 'payment' else 'cancel_period'
        if self.id < self.same_periods[0].id:
            if self.sign == 'cancellation':
                # I'm the first to be received, and I'm a cancellation. There
                # cannot be a matching payment, because it would have been
                # received before me
                return 'cancel_period'
        elif self.sign == 'payment':
            # I'm not the first period on these dates, and I'm a payment, so I
            # cannot be treated before the previous periods are done
            return 'new_period'

        # Remaining cases : I'm a cancellation for a not yet treated payment,
        # or I'm the first not yet treated payment which will be cancelled
        if (self.sign == 'cancellation' and self.id > self.same_periods[0].id
                and (len(self.same_periods) == 1
                    or self.id < self.same_periods[1].id)):
            # self.same_periods[0] is probably the payment that I am cancelling
            return 'cancellation_non_paid'
        if (self.sign == 'payment' and self.id < self.same_periods[0].id
                and self.same_periods[0].sign == 'cancellation'):
            # self.same_periods[0] is going to cancel me :'(
            return 'cancelled_non_paid_period'

        # Just in case
        return 'no_automatic'

    def getter_claim(self, name):
        if not self.service:
            return None
        return self.service.claim.id

    def getter_indemnification(self, name):
        if not self.indemnification:
            return None
        value = getattr(self.indemnification, name[16:], None)
        if name[16:] in ('beneficiary',):
            value = value.id if value else None
        return value

    @classmethod
    def getter_main_kind(cls, periods, name):
        Detail = Pool().get('claim.ij.period.line')

        lines = Detail.search([('period', 'in', periods),
                ('kind', 'in', list(INDEMN_KINDS))])

        kinds = {}
        for line in lines:
            kinds[line.period.id] = line.kind
        return kinds

    def getter_number_of_days(self, name):
        if not self.end_date:
            return None
        return (self.end_date - self.start_date).days + 1

    @classmethod
    def getter_other_periods(cls, periods, name):
        per_subscription = {x.subscription.id: set() for x in periods}

        others = cls.__table__()
        me = cls.__table__()
        cursor = Transaction().connection.cursor()

        cursor.execute(*me.join(others,
                condition=(others.subscription == me.subscription)
                ).select(others.subscription, others.id,
                where=others.subscription.in_(
                    [x.subscription.id for x in periods])
                & (others.state != Literal('treated')),
                order_by=[others.start_date, others.id]))

        for period, other_id in cursor.fetchall():
            per_subscription[period].add(other_id)

        return {p.id:
            [x for x in per_subscription[p.subscription.id] if p.id != x]
            for p in periods}

    @classmethod
    def getter_party(cls, periods, name):
        Party = Pool().get('party.party')

        per_ssn = defaultdict(list)
        for period in periods:
            per_ssn[period.subscription.ssn].append(period.id)

        matches = Party.search([('ssn', 'in', per_ssn.keys())])

        result = {}
        for party in matches:
            result.update({
                    x: party.id for x in per_ssn[party.ssn]})

        return result

    def getter_same_periods(self, name):
        return [x.id for x in self.other_periods
            if self.start_date == x.start_date and self.end_date == x.end_date]

    @classmethod
    def getter_service(cls, periods, name):
        pool = Pool()
        benefits = pool.get('benefit').prest_ij_benefits()

        service = pool.get('claim.service').__table__()
        loss = pool.get('claim.loss').__table__()
        contract = pool.get('contract').__table__()
        subscriber = pool.get('party.party').__table__()
        party = pool.get('party.party').__table__()
        subscription = pool.get('claim.ij.subscription').__table__()
        period = cls.__table__()

        cursor = Transaction().connection.cursor()

        cursor.execute(*period.join(subscription, condition=(
                    period.subscription == subscription.id)
                ).join(subscriber, condition=(
                    subscription.siren == subscriber.siren)
                ).join(party, condition=subscription.ssn == party.ssn
                ).join(loss, condition=loss.covered_person == party.id
                ).join(service, condition=service.loss == loss.id
                ).join(contract, condition=(service.contract == contract.id
                    ) & (contract.subscriber == subscriber.id)
                ).select(period.id, service.id,
                where=service.benefit.in_([x.id for x in benefits])
                & ((loss.start_date == Null)
                    | (loss.start_date <= period.start_date))
                & ((loss.end_date == Null)
                    | (loss.end_date >= period.end_date))
                & (service.eligibility_status == 'accepted')
                & period.id.in_([x.id for x in periods])
                ))

        result = {x.id: None for x in periods}
        result.update(dict(cursor.fetchall()))
        return result

    def getter_subscriber(self, name):
        return self.subscription.subscriber.id

    def getter_total_amount(self, name):
        return self.indemnification_amount + self.taxes_amount

    @classmethod
    def selector_indemnification_status(cls):
        Indemnification = Pool().get('claim.indemnification')
        return [(x[0], coog_string.translate(Indemnification, 'status',
                    x[1], 'selection'))
            for x in Indemnification.status.selection]

    @classmethod
    def search_party(cls, name, clause):
        _, operator, value = clause

        if operator == 'in' and not value:
            return [('id', '<', 0)]

        Operator = tryton_fields.SQL_OPERATORS[operator]

        pool = Pool()

        period = cls.__table__()
        subscription = pool.get('claim.ij.subscription').__table__()
        party = pool.get('party.party').__table__()

        query = period.join(subscription, condition=(
                period.subscription == subscription.id)
            ).join(party, condition=subscription.ssn == party.ssn
            ).select(period.id, where=Operator(party.id, value))

        return [('id', 'in', query)]

    def get_currency(self):
        # If our subscription does not have a subscriber, we have some other
        # problems anyway
        return self.subscription.subscriber.currency

    @classmethod
    def mark_as_treated(cls, periods):
        assert all(x.state == 'received' for x in periods)
        cls.write(periods, {'state': 'treated'})

    @classmethod
    def process_zip_file(cls, path):
        zip_file = ZipFile(path)
        for data_file in zip_file.namelist():
            with zip_file.open(data_file, 'r') as fd_:
                element = etree.fromstring(fd_.read())
                if element.attrib.get('Nature', '') == 'BPIJ':
                    cls._process_bpij_file(element)
                    return True
        return False

    @classmethod
    def _process_bpij_file(cls, tree):
        pool = Pool()
        Subscription = pool.get('claim.ij.subscription')

        ns = {'n': BPIJ_NS[1:-1]}

        def node_func(base, key, value=False):
            node = base.xpath('n:%s' % key, namespaces=ns)
            if not value:
                return node
            return node[0].text

        saver = model.Saver(cls)
        reception_date = datetime.datetime.strptime(
            node_func(tree, 'Temps', True)[:19], '%Y-%m-%dT%H:%M:%S')
        to_process = []
        for institution in node_func(tree, 'Declarant'):
            total_instit = Decimal(
                node_func(institution, 'Cumul/n:Montant', True))
            cur_total_instit = 0
            for subscriber in node_func(institution, 'Declare'):
                siren = node_func(subscriber, 'Identite', True)[:-5]
                total_subscriber = Decimal(
                    node_func(subscriber, 'Cumul/n:Montant', True))
                cur_total_subscriber = 0
                for sub_instit in node_func(subscriber, 'Caisse'):
                    accounting_date = datetime.datetime.strptime(
                        node_func(sub_instit, 'JComptable', True),
                        '%Y-%m-%d+%H:%M').date()
                    for party in node_func(sub_instit, 'Assure'):
                        ssn = node_func(party, 'NIR', True)
                        subscription, = Subscription.search(
                            [('ssn', 'like', '%s%%' % ssn),
                                ('siren', '=', siren)])
                        periods, total = cls._process_periods(subscription,
                            party, node_func)
                        for period in periods:
                            period.accounting_date = accounting_date
                            period.reception_date = reception_date
                        if periods:
                            to_process.append(subscription)
                            saver.extend(periods)
                        cur_total_subscriber += total or 0
                assert total_subscriber == cur_total_subscriber
                cur_total_instit += total_subscriber
            assert cur_total_instit == total_instit
        saver.finish()

        if to_process:
            Subscription.finalize_add_periods(to_process)

    @classmethod
    def _process_periods(cls, subscription, data, node_func):
        periods = []
        amount = Decimal(0)
        for main_period in node_func(data, 'Assurance'):
            kind = node_func(main_period, 'CodeNature', True)
            parsed = defaultdict(list)
            for sub_period in node_func(main_period, 'Prestation'):
                data = {}
                for node in sub_period:
                    data[node.tag[len(BPIJ_NS):]] = node.text
                parsed[data['DateDebPrest']].append(data)
            for period_data in parsed.itervalues():
                new_period = cls._new_period(period_data)
                new_period.subscription = subscription
                new_period.period_kind = kind
                amount += sum(x.total_amount for x in new_period.lines)
                periods.append(new_period)

        return periods, amount

    @classmethod
    def _new_period(cls, period_data):
        Line = Pool().get('claim.ij.period.line')
        period = cls()

        lines = []
        total = Decimal(0)
        for data in period_data:
            line = Line()
            line.kind = data['CodeNature']
            if data['DateDebPrest']:
                period.start_date = datetime.datetime.strptime(
                    data['DateDebPrest'], '%Y-%m-%d+%H:%M').date()
            if 'DateFinPrest' in data:
                period.end_date = datetime.datetime.strptime(
                    data['DateFinPrest'], '%Y-%m-%d+%H:%M').date()
            line.number_of_days = int(data.get('NbIJ', '0'))
            period.beneficiary_kind = 'company' if data['IJSub'] == 'true' \
                else 'party'
            line.amount = Decimal(data.get('PU', '0'))
            line.total_amount = Decimal(data['Montant'])
            total += line.total_amount
            lines.append(line)
        period.lines = lines
        period.sign = 'payment' if total >= 0 else 'cancellation'
        return period

    @classmethod
    def add_to_indemnifications(cls, periods, indemnifications):
        per_dates = defaultdict(list)
        per_indemn = {}

        for i in indemnifications:
            per_dates[(i.start_date, i.end_date)].append(i)
            per_dates[i.start_date].append(i)
            per_dates[i.end_date].append(i)
            per_indemn[i] = list(getattr(i, 'prestij_periods', []))

        for p in periods:
            if (p.start_date, p.end_date) in per_dates:
                indemn = per_dates[p.start_date, p.end_date][0]
            elif p.start_date in per_dates:
                indemn = per_dates[p.start_date][0]
            elif p.end_date in per_dates:
                indemn = per_dates[p.end_date][0]
            else:
                indemn = indemnifications[0]
            indemn_periods = per_indemn[indemn]
            indemn_periods.append(p)

        for indemn, periods in per_indemn.iteritems():
            indemn.prestij_periods = periods


class ClaimIjPeriodLine(model.CoogSQL, model.CoogView, ModelCurrency):
    'Claim Ij Period Line'

    __name__ = 'claim.ij.period.line'

    period = fields.Many2One('claim.ij.period', 'Period', required=True,
        ondelete='CASCADE', select=True)
    kind = fields.Selection(LINE_KINDS, 'Kind', readonly=True)
    number_of_days = fields.Integer('Number of Days', domain=[
            ('number_of_days', '>=', 0)], readonly=True)
    amount = fields.Numeric('Amount', digits=(16, 2), readonly=True)
    total_amount = fields.Numeric('Total Amount', digits=(16, 2),
        readonly=True)

    @classmethod
    def validate(cls, lines):
        super(ClaimIjPeriodLine, cls).validate(lines)
        allowed = INDEMN_KINDS | TAXES_KINDS
        for line in lines:
            if line.amount:
                assert abs(line.total_amount) == abs(
                    line.amount * line.number_of_days), \
                    'Inconsistent amount data'
            assert line.kind in allowed, 'Unallowed kind %s' % line.kind

    def get_currency(self):
        return self.period.currency

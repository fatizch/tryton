# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import datetime
from zipfile import ZipFile
from lxml import etree
from io import BytesIO

from trytond.model import Unique
from trytond.config import config
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.model import Workflow, dualmethod
from trytond.pool import Pool
from trytond.tools import memoize

from trytond.modules.coog_core import model, fields, utils

import gesti_templates


__all__ = [
    'ClaimIjSubscriptionRequestGroup',
    'ClaimIjSubscriptionRequest',
    'ClaimIjSubscription',
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
    def generate_identification(cls):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        ClaimConfiguration = pool.get('claim.configuration')
        claim_config = ClaimConfiguration.get_singleton()
        sequence = claim_config.prest_ij_sequence
        assert sequence
        return Sequence.get_id(sequence.id)

    @property
    def _identification(self):
        assert self.identification
        return self.identification

    def get_prefixed_id(self, prefix):
        return '-'.join([prefix, self._identification])

    @classmethod
    def get_unprefixed_id(cls, file_id, kind):
        prefix = cls.get_prefix(kind)
        return file_id[len(prefix) + 1:]

    @classmethod
    def get_prefix(cls, kind):
        # if kind == 'header':
        #     return 'E-GESTIP'
        # elif kind == 'document':
        #     return 'D-GESTIP'
        # this code above is according to CNAM

        # below is the publiflux implementation
        code_ga = cls.get_ij_conf_item('code_ga')
        return code_ga

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
            'ENTARLGESTIP': 'arl_header',
            'ENTCRGESTIP': 'cr_header',
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
        doc_diags = doc.xpath("//n:DiagDocument/n:Diagnostic",
            namespaces=ns_arg)
        for doc_diag in doc_diags:
            siren = doc_diag.xpath('n:Entreprise/n:Identite/text()',
                    namespaces=ns_arg)
            assert siren, 'No identity for diagnostic element %s' \
                % etree.tostring(doc_diag, pretty_print=True,
                    encoding='utf8')
            siren = siren[0]
            requests = group.get_requests_from_diagnostic_data(siren)
            assert requests, 'No IJ requests found for siren %s for document ' \
                'id %s' % (siren, doc_id)
            op_state = doc_diag.xpath('n:Etat/text()', namespaces=ns_arg)[0]
            if op_state == 'R':
                op_reject_cause = doc_diag.xpath('n:Cause/text()',
                        namespaces=ns_arg)[0]
                op_reject_label = doc_diag.xpath('n:Libelle/text()',
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

    def get_requests_from_diagnostic_data(self, siren):
        return [x for x in self.requests if x.subscription.siren == siren]


class ClaimIjSubscriptionRequest(Workflow, model.CoogSQL, model.CoogView):
    'Claim IJ Subscription Request'

    __name__ = 'claim.ij.subscription_request'

    date = fields.Date('Date', readonly=True, required=True)
    state = fields.Selection(SUBSCRIPTION_REQUEST_STATES, 'State',
        required=True, readonly=True, select=True)
    operation = fields.Selection([('cre', 'CRE'), ('sup', 'SUP')],
        'Operation', readonly=True)
    subscription = fields.Many2One('claim.ij.subscription', 'Subscription',
        required=True, readonly=True, ondelete='RESTRICT', select=True)
    siren = fields.Function(
        fields.Char('Siren'),
        'on_change_with_siren')
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

    @classmethod
    def __setup__(cls):
        super(ClaimIjSubscriptionRequest, cls).__setup__()
        cls._transitions |= set((
                ('unprocessed', 'processing'),
                ('processing', 'failed'),
                ('processing', 'confirmed'),
                ))

    @classmethod
    def default_state(cls):
        return 'unprocessed'

    @fields.depends('subscription')
    def on_change_with_siren(self, name=None):
        return self.subscription.siren if self.subscription else ''

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


class ClaimIjSubscription(model.CoogSQL, model.CoogView):
    'Claim IJ Subscription'

    __name__ = 'claim.ij.subscription'

    parties = fields.Function(
        fields.Many2Many('party.party', None, None, 'Parties'),
        'getter_parties')
    siren = fields.Char('Siren', readonly=True)
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
        order=[('date', 'DESC')])
    requests_event_logs = fields.Function(
        fields.Many2Many('event.log', None, None, 'Requests Event Logs'),
        'get_requests_event_logs')
    activated = fields.Boolean('Activated', readonly=True)
    ij_activation = fields.Function(fields.Boolean('IJ Activation', states={
                'readonly': Bool(Eval('activated')),
                }, depends=['activated']),
        'on_change_with_ij_activation', setter='setter_ij_activation')

    @classmethod
    def __setup__(cls):
        super(ClaimIjSubscription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [('unique_subscription',
                Unique(t, t.siren), 'There must be only one IJ subscription '
                'per siren')]
        cls._buttons.update({
                'button_relaunch_process': {
                    'readonly': (Eval('state') != 'in_error')},
                })

    @classmethod
    def default_siren(cls):
        active_id = Transaction().context.get('active_id')
        if active_id:
            return Pool().get('party.party')(active_id).siren

    @classmethod
    def default_state(cls):
        return 'undeclared'

    def getter_parties(self, name):
        if not self.siren:
            return []
        return sorted([x.id for x in Pool().get('party.party').search(
                    [('siren', '=', self.siren)])])

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
    def create_subcription_requests(cls, subscriptions, operation, date):
        return Pool().get('claim.ij.subscription_request').create([{
                    'date': date,
                    'subscription': sub,
                    'operation': operation
                    } for sub in subscriptions])

    @classmethod
    @model.CoogView.button_action(
        'claim_prest_ij_service.act_relaunch_ij_subscription')
    def button_relaunch_process(cls, subscriptions):
        pass

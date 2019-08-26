# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import requests
import json

from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.config import config
from trytond.pyson import Eval
from trytond.modules.coog_core import fields, model


__all__ = [
    'ReportGenerate',
    'ReportTemplate',
    ]


class ReportGenerate(metaclass=PoolMeta):
    __name__ = 'report.generate'

    @classmethod
    def generate_message_header(cls, selected_letter, records):
        apiKey = config.get('primotexto', 'key')
        return {
            'X-Primotexto-ApiKey': apiKey,
            'Content-Type': 'application/json',
            }

    @classmethod
    def process_primotexto(cls, ids, data, **kwargs):
        return cls.process_send_text_message(ids, data, **kwargs)

    @classmethod
    def generate_message_data(cls, selected_letter, record):
        data = super(ReportGenerate, cls).generate_message_data(
            selected_letter, record)
        if selected_letter.genshi_evaluated_category:
            data['category'] = \
                selected_letter.genshi_evaluated_category.encode('utf-8')
        if selected_letter.genshi_evaluated_campaign_name:
            data['campaignName'] = \
                selected_letter.genshi_evaluated_campaign_name.encode('utf-8')
        return data

    @classmethod
    def primotexto_send_message(cls, headers, data, selected_letter):
        apiUrl = config.get('primotexto', 'url')
        return requests.post(apiUrl, headers=headers,
            data=json.dumps(data))

    @classmethod
    def check_send_errors(cls, response, process_method):
        ReportTemplate = Pool().get('report.template')
        try:
            result = json.loads(response.text)
        except ValueError:
            result = {}
        if process_method == 'primotexto' and not response.ok:
            if result.get('code'):
                raise UserError(
                    gettext('report_engine_primotexto.msg_primotexto_failed',
                        code=result.get('code')))
            elif result.get('status'):
                raise UserError(
                    gettext('report_engine_primotexto.msg_primotexto_url_error',
                        code=result.get('status'),
                        reason=result.get('error')))
            raise UserError(
                gettext('report_engine_primotexto.msg_primotexto_url_error',
                code=response.status_code,
                reason=response.reason or ''))
        if (process_method == 'primotexto' and response.ok
                and not result.get('snapshotId')):
            raise UserError(
                gettext('report_engine_primotexto.msg_primotexto_url_error',
                code='200',
                reason=gettext(
                        'report_engine_primotexto.msg_primotexto_no_return')))

        return super(ReportGenerate, cls).check_send_errors(response,
            process_method)


@model.genshi_evaluated_fields('campaign_name', 'category')
class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    logger = logging.getLogger(__name__)

    campaign_name = fields.Char('Campaign Name',
        states={
            'invisible': Eval('process_method') != 'primotexto'
            }, depends=['process_method'])
    category = fields.Char('Category',
        states={
            'invisible': Eval('process_method') != 'primotexto'
            }, depends=['process_method'])

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        for param in ('url', 'key'):
            required_param = config.get('primotexto', param)
            if not required_param:
                cls.logger.warning('[PRIMOTEXTO]: variable %s is not set '
                    'in the primotexto section. It is required to send text '
                    'messages.' % param)

    @fields.depends('input_kind')
    def get_possible_process_methods(self):
        if self.input_kind == 'text_message':
            return super(ReportTemplate, self).get_possible_process_methods(
                ) + [('primotexto',
                        gettext(
                            'report_engine_primotexto.msg_input_primotexto'))]
        return super(ReportTemplate, self).get_possible_process_methods()

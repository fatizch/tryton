# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.cache import Cache
from trytond.pool import Pool, PoolMeta
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'ReportTemplate',
    'ReportGenerate',
    ]


class ReportTemplate:
    __name__ = 'report.template'

    generate_event_logs = fields.Boolean('Generate Event Logs')

    _do_generate_event_logs_cache = Cache('_do_generate_event_logs')

    @staticmethod
    def default_generate_event_logs():
        return False

    @classmethod
    def do_generate_event_logs(cls, data):
        _object = cls._do_generate_event_logs_cache.get(
                data['id'])
        if _object is None:
            pool = Pool()
            Event = pool.get('event')
            model = pool.get(data['model'])
            report_template = pool.get('report.template')(
                data['doc_template'][0])
            _object = model.search( [('id', '=', data['id']),])
            cls._do_generate_event_logs_cache.set(data['id'],
                    _object[0].id)
        if report_template.generate_event_logs :
            Event.notify_events(_object,'generate_report',
                report_template.name)


class ReportGenerate:
    __metaclass__ = PoolMeta
    __name__ = 'report.generate'

    @classmethod
    def execute(cls, ids, data):
        result = super(ReportGenerate, cls).execute(ids, data)
        report_template = Pool().get('report.template')
        report_template.do_generate_event_logs(data)
        return result


class ReportGenerateFromFile:
    __metaclass__ = PoolMeta
    __name__ = 'report.generate_from_file'

    @classmethod
    def execute(cls, ids, data):
        result = super(ReportGenerateFromFile, cls).execute(ids, data)
        report_template = Pool().get('report.template')
        report_template.do_generate_event_logs(data)
        return result

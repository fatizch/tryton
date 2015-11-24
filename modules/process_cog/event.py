from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:

    __name__ = 'event.type.action'

    process_to_initiate = fields.Many2One('process', 'Process To Initiate',
        ondelete='RESTRICT', states={'invisible': Eval('action') !=
            'initiate_process'})

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('initiate_process', 'Initiate Process')]

    @classmethod
    def _export_light(cls):
        return super(EventTypeAction, cls)._export_light() | {
            'process_to_initiate'}

    def execute(self, objects, event_code):
        pool = Pool()
        Event = pool.get('event')
        Process = pool.get('process')
        if self.action != 'initiate_process':
            return super(EventTypeAction, self).execute(objects, event_code)
        process_id = self.process_to_initiate
        if not process_id:
            return
        process = Process(process_id)
        state = process.first_step()
        Model = pool.get(objects[0].__name__)
        assert Model.__name__ == process.on_model.model
        ok, not_ok = [], []
        [ok.append(x) if not x.current_state else not_ok.append(x)
            for x in objects]
        if ok:
            Model.write(ok, {'current_state': state})
        if not_ok:
            Event.notify_events(not_ok, 'process_not_initiated',
                description=process.technical_name)

    def cache_data(self):
        data = super(EventTypeAction, self).cache_data()
        data['process_to_initiate'] = self.process_to_initiate.id if \
            self.process_to_initiate else None
        return data

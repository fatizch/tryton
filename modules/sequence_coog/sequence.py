# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.conditionals import Coalesce
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Or, And, If

from trytond.modules.coog_core import fields, model, utils
from trytond.server_context import ServerContext


__all__ = [
    'Sequence',
    'SequenceStrict',
    ]


class Sequence(model.CoogSQL):
    __metaclass__ = PoolMeta
    __name__ = 'ir.sequence'

    sub_order = fields.Integer('Sub order')
    max_number = fields.Integer('Max Number', states={
            'invisible': Or(~Eval('type').in_(['incremental']),
                Bool(Eval('sub_sequences'))),
            }, depends=['type', 'sub_sequences'])
    sub_sequences = fields.One2Many('ir.sequence', 'parent',
        'Sub Sequences', states={
            'invisible': Bool(Eval('parent')),
            }, domain=[
            ('type', '=', 'incremental'),
            ('code', '=', Eval('code'))
            ],
        depends=['parent', 'code'],
        order=[('start_date', 'ASC'), ('sub_order', 'ASC')])
    parent = fields.Many2One('ir.sequence', 'Parent',
        states={
            }, ondelete='CASCADE', select=True)
    start_date = fields.Date('Start Date', states={
            'invisible': ~Eval('parent'),
            }, depends=['parent'])
    end_date = fields.Date('End Date', states={
            'invisible': ~Eval('parent'),
            }, depends=['parent'])
    iteration_before_notification = fields.Integer(
        'Iteration(s) Before Notification', states={
            'invisible': (Eval('type') != 'incremental') | Bool(Eval('parent')),
            }, depends=['type', 'parent'], help='Integer which defines how'
        ' much sequence(s) it must remains before sending a notification')

    @classmethod
    def __setup__(cls):
        super(Sequence, cls).__setup__()
        cls._error_messages.update({
                'sequence_max_number_exceeded': 'Coog can\'t assign a new'
                ' number for the sequence "%(sequence_name)s": The limit is'
                ' of %(number_max)s is reached. Please define a new sub-'
                'sequence period or increase limits',
                'no_sequence_at_date': 'Could not get a valid sub-sequence'
                ' at date %(date)s for the sequence "%(sequence)s".'
                ' Please define a new sub-sequence period on increase limits',
                'period_invalid': 'The sub-sequence period is invalid:'
                ' %(start_date)s greater than %(end_date)s',
                })
        for field_ in ('prefix', 'suffix', 'type', 'padding',
                'timestamp_rounding', 'number_increment'):
            field_ = getattr(cls, field_)
            if 'invisible' not in field_.states:
                field_.states['invisible'] = False
            if 'required' not in field_.states:
                field_.states['required'] = False
            field_.states['invisible'] = Or(field_.states['invisible'],
                Bool(Eval('sub_sequences')))
            field_.states['required'] = And(field_.states['required'],
                ~Eval('sub_sequences'))
            field_.depends.append('sub_sequences')
        cls.type.domain = [If(~Eval('sub_sequences'), cls.type.domain,
                [('type', '=', 'incremental')])]
        cls.type.depends.append('sub_sequences')

    @classmethod
    def validate(cls, records):
        super(Sequence, cls).validate(records)
        with model.error_manager():
            for record in records:
                start_date = record.start_date or datetime.date.min
                end_date = record.end_date or datetime.date.max
                if start_date > end_date:
                    cls.append_functional_error('period_invalid', {
                            'start_date': start_date,
                            'end_date:': end_date,
                            })

    @classmethod
    def set_number_next(cls, sequences, name, value):
        sequences = [s for s in sequences if not s.sub_sequences]
        with model.error_manager():
            for sequence in sequences:
                if (sequence.max_number is not None
                        and value > sequence.max_number):
                    cls.append_functional_error(
                        'sequence_max_number_exceeded', {
                            'sequence_name': sequence.name,
                            'number_max': sequence.max_number,
                            })
        super(Sequence, cls).set_number_next(sequences, name, value)

    @staticmethod
    def order_start_date(tables):
        table, _ = tables[None]
        return [Coalesce(table.start_date, datetime.date.min)]

    @staticmethod
    def order_end_date(tables):
        table, _ = tables[None]
        return [Coalesce(table.end_date, datetime.date.max)]

    def get_number_next(self, name):
        if not self.sub_sequences:
            return super(Sequence, self).get_number_next(name)
        return self.get_valid_sequence_at_date().get_number_next(name)

    def get_valid_sequence_at_date(self, at_date=None):
        at_date = at_date or ServerContext().get('sequence_date',
            utils.today())
        sequences_at_date = []
        for sub_sequence in self.sub_sequences:
            start_date = sub_sequence.start_date or datetime.date.min
            end_date = sub_sequence.end_date or datetime.date.max
            if at_date >= start_date and at_date <= end_date:
                sequences_at_date.append(sub_sequence)
        if sequences_at_date:
            for sequence in sequences_at_date:
                if (not sequence.max_number
                        or sequence.number_next <= sequence.max_number):
                    return sequence

        self.raise_user_error('no_sequence_at_date', {
                'date': at_date,
                'sequence': self.name,
                })

    @classmethod
    def _get_sequence(cls, sequence):
        Event = Pool().get('event')
        prefix, suffix = '', ''
        if not sequence.sub_sequences:
            value = super(Sequence, cls)._get_sequence(sequence)
            if sequence.max_number and int(value) > sequence.max_number:
                cls.raise_user_error('sequence_max_number_exceeded', {
                        'sequence_name': sequence.name,
                        'number_max': sequence.max_number,
                        })
        else:
            valid_sequence = sequence.get_valid_sequence_at_date()
            value = valid_sequence._get_sequence(valid_sequence)
            prefix, suffix = valid_sequence.prefix, valid_sequence.suffix
        if (sequence.type == 'incremental' and sequence.max_number
                and sequence.max_number - int(value) <=
                sequence.iteration_before_notification):
            Event.notify_events([sequence],
                'sequence_limit_notification')
        return '%s%s%s' % (prefix, value, suffix)


class SequenceStrict(Sequence):
    __metaclass__ = PoolMeta
    __name__ = 'ir.sequence.strict'

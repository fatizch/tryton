# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import batch, utils


class BaseMassFlowBatch(batch.MemorySavingBatch):
    @classmethod
    def write_header(cls, *args, **kwargs):
        filename = cls.get_filename(*args, **kwargs)
        header_values = [x[0]
                for x in cls.object_fields_mapper(*args, **kwargs)]
        with utils.safe_open(filename, 'ab') as fo_:
            fo_.write(cls.line_definition(*args, **kwargs) %
                    tuple(header_values) + '\n')

    @classmethod
    def check_mandatory_parameters(cls, *args, **kwargs):
        assert cls.get_flush_size(*args, **kwargs), 'flush_size is required'
        assert cls.get_filename(*args, **kwargs), 'output_filename is required'

    @classmethod
    def data_separator(cls, *args, **kwargs):
        """
        Return the separator to use between each data of the line
        """
        return ';'

    @classmethod
    def object_fields_mapper(cls, *args, **kwargs):
        """
        Return a list of tuple which the first element
        is the column name and the second element, the way to get it's value.
        For instance:
        return [('Id', lambda *largs: largs[0])]
        """
        return []

    @classmethod
    def line_definition(cls, *args, **kwargs):
        """
        Returns the line pattern using the data_separator and the
        number of mapped fields returned by the method "object_fields_mapper":
        For instance if we have 3 mapped fields and ';' as data separator:
        "%s;%s;%s"
        """
        return cls.data_separator().join(
            ['%s' for x in cls.object_fields_mapper(*args, **kwargs)])

    @classmethod
    def sanitize(cls, value):
        return value

    @classmethod
    def format_object(cls, object, *args, **kwargs):
        """
        Should return a list of values to write into the flow
        file. All values are sanitized.
        """
        return [cls.sanitize(_getter(object, fname)) for fname, _getter in
            cls.object_fields_mapper(*args, **kwargs)]

    @classmethod
    def format_lines(cls, objects, *args, **kwargs):
        """
        Creates a formatted string depending on format_object and
        the defined line_definition method.
        """
        for object in objects:
            yield cls.line_definition(*args, **kwargs) % tuple(
                cls.format_object(object, *args, **kwargs))

    @classmethod
    def line_writer(cls, filename, lines, *args, **kwargs):
        """
        Defines how the lines are flushed.
        Lines is a generator expression and we use flush_size argument
        to control the memory usage when flushing data.
        """
        flush_size = int(cls.get_flush_size(*args, **kwargs))
        for lines in utils.iterator_slice(lines, flush_size):
            with utils.safe_open(filename, 'ab') as fo_:
                fo_.write('\n'.join(lines) + '\n')

    @classmethod
    def get_filename(cls, *args, **kwargs):
        return kwargs.get('output_filename')

    @classmethod
    def get_flush_size(cls, *args, **kwargs):
        return kwargs.get('flush_size')

    @classmethod
    def execute(cls, objects, ids, *args, **kwargs):
        """
        It behaves the same way but "objects" are not automatically browsed:
        these objects are returned by the parse_select_ids method.
        So you must define a parse_select_ids which returns a generator
        expression to properly save the memory.
        """
        super(BaseMassFlowBatch, cls).execute(objects, ids, *args, **kwargs)
        lines = (line for line in cls.format_lines(objects, *args, **kwargs))
        cls.line_writer(cls.get_filename(*args, **kwargs), lines,
                *args, **kwargs)

# Needed for serializing data
import json

# Needed for proper encoding / decoding of objects as strings
from trytond.protocols.jsonrpc import JSONEncoder, object_hook
from trytond.model import fields
from trytond.pool import Pool
from trytond.model import Model

from .utils import to_list

__all__ = ['WithAbstract']


class WithAbstract(object):
    'With Abstract'
    # This class is a tool class which contains a set of methods allowing the
    # use (creation, modification, saving) of Active Record objects with
    # storage through a string.
    #
    # The main purpose of doing this is to provide a way for transferring data
    # in object form with no need to store them.
    #
    # This is particularly useful in a wizard context, where you may need a way
    # to pass an object from one state to another, without having to store it
    # in the database in an incomplete form.
    #
    # USAGE :
    # You need to tweak the __setup__ code of your class to match the content
    # of that of ProcessState in order for the WithAbstract tools to be
    # functionnal.
    #
    # Basically, you must declare the '__abstracts__' variable in your class
    # and set it with a list of tuples with the following pattern :
    #     __abstracts__ = [(field_name, model_name)]
    #
    # With this done, you can access those objects through the use of
    # 'get_abstract_objects' and 'store_abstract_objects' to get your object,
    # play with it, then store it.

    @staticmethod
    def create_field(field_desc, value):
        # This method is used to get what will be set in the field_desc of the
        # object you currently are working on.

        if isinstance(value, list):
            # If the value is a list
            res = []
            if not len(value) > 0:
                return res

            # then the field_desc must be a list-compatible field desc
            if isinstance(field_desc, (
                    fields.One2Many,
                    fields.Many2Many)):
                # We need to get the model of the target.
                if isinstance(field_desc, fields.Many2Many):
                    # In the case of a Many2Many, it is necessary to go through
                    # the relation model, as there is no direct access in the
                    # field description to the target model.
                    relation_model = Pool().get(field_desc.relation_name)
                    rel_field = relation_model._fields[field_desc.target]
                    for_model = rel_field.model_name
                else:
                    for_model = field_desc.model_name

                # Then we treat each element separately
                for elem in value:
                    if isinstance(elem, Model):
                        # If it already is a Model (that is an instance of the
                        # model_name, we just append it.
                        res.append(elem)
                    elif isinstance(elem, (dict, int, long)):
                        # If not, we assume its value will allow us to create
                        # or find a record.
                        res.append(WithAbstract.create_abstract(
                            for_model,
                            elem))
                    else:
                        # Anything else is wrong.
                        raise BadDataKeyError
        elif isinstance(value, Model):
            # If the value is a model
            if isinstance(field_desc, (fields.Many2One, fields.Reference)):
                # and the field is a M2O or a Reference (a one on one field),
                # it's all done !
                res = value
            else:
                # If you try to assign a Model to another field kind, error.
                raise BadDataKeyError
        elif isinstance(value, dict) and isinstance(
                field_desc, (fields.Many2One, fields.Reference)):
            # If the value is a dict and the expected field value an instance,
            # we assume that we can create it then go !
            res = WithAbstract.create_abstract(field_desc.model_name, value)
        elif isinstance(value, str) and isinstance(
                field_desc, (fields.Reference)):
            try:
                model_name, id = value.split(',')
            except Exception:
                raise
            model_obj = Pool().get(model_name)
            return model_obj(id)
        elif (isinstance(field_desc, fields.Many2One) and
                isinstance(value, (int, long))):
            # Case of a Relation Field being stored as an integer.
            ModelObject = Pool().get(field_desc.model_name)
            res = ModelObject(value)
        else:
            # Any basic type (string, int, etc...) in a non model-link context
            # is a direct set.
            res = value
        return res

    @staticmethod
    def load_from_text(model_name, data):
        # This method is just an entry point that will decode the encoded text
        # into a dict that is then passed as a value for the object we are
        # trying to create.
        data_text = json.loads(data.encode('utf-8'), object_hook=object_hook)
        return WithAbstract.create_abstract(model_name, data_text)

    # This method will be use to create an AbstractObject from a value,
    # whatever the value type.
    @staticmethod
    def create_abstract(model, data):
        ForModel = Pool().get(model)
        if isinstance(data, (int, long)):
            # It is an id, we create the object and specify it
            return ForModel(data)
        elif isinstance(data, dict):
            # It is a dictionnary, we assume that it matches the model's fields
            # and instanciate it :
            for_object = ForModel()
            for key, value in data.iteritems():
                # We go through each value of the dictionnary an set it.
                if not key in for_object._fields:
                    # After checking that it matches, of course...
                    raise BadDataKeyError
                setattr(for_object,
                        key,
                        WithAbstract.create_field(for_object._fields[key],
                                                  value))
            return for_object
        elif isinstance(data, str):
            # There might be recursive serialization, so me must account for it
            data_dict = WithAbstract.load_from_text(data)
            return WithAbstract.create_abstract(model, data_dict)
        else:
            raise TypeError
        # Anything else is an error...

    @staticmethod
    def get_abstract_object(session, field_name):
        # This method takes a session, a field_name, and give back an object
        # based on the field_name.
        #
        # TODO :
        #  - remove the 'process_state', the first parameter should be the
        # object which has field_name in its __abstracts__ field.

        result = getattr(session.process_state, field_name + '_db')
        # We need to use the '_db' field to get the model.
        if not result.id:
            # If the object is not stored in the database, we will try to get
            # it from serialization value.
            src_text = getattr(session.process_state, field_name + '_str')
            if src_text:
                # It's already been serialized, so we load and return it.
                result = WithAbstract.load_from_text(result.__name__, src_text)
            else:
                # It really is the first time this object is needed, so we just
                # instanciate it.
                ForModel = Pool().get(result.__name__)
                result = ForModel()
        return result

    @staticmethod
    def serialize_field(field, from_field=None):
        # We need a way to serialize fields so that they become json compatible
        # for storing while still being readable when extracting.
        res = None
        if (isinstance(field, list) and
                field != [] and
                isinstance(field[0], Model)):
            # It the provided field is a list, and the elements of this list is
            # a Model, we need to serialize each element before use.
            res = []
            for elem in field:
                res.append(WithAbstract.serialize_field(elem))
        elif isinstance(field, Model):
            # If the field is a model
            if isinstance(field, Model) and field.id > 0:
                # that has been stored in the db, we just need its id to store
                # it.
                res = field.id
                if isinstance(from_field, fields.Reference):
                    res = '%s,%s' % (
                        field.__name__,
                        field.id)
            else:
                # If not, we need to go through each field to serialize each of
                # them separately.
                res = {}
                if not field._values is None:
                    for key, value in field._values.iteritems():
                        res[key] = WithAbstract.serialize_field(
                            value,
                            field._fields[key])
        else:
            # If the field is a basic type, no need for further work.
            res = field

        return res

    @staticmethod
    def store_to_text(for_object):
        # Storing to text is easy, we serialize our object, then create a json
        # string from it.
        return json.dumps(WithAbstract.serialize_field(for_object),
                          cls=JSONEncoder)

    @staticmethod
    def save_abstract_object(session, field_name, for_object):
        # Saving the object means serializing it in a json-compatible string,
        # then storing it in the dedicated field.
        #
        # TODO :
        #  - same as get_abstract_object

        setattr(session.process_state, field_name + '_str',
                WithAbstract.store_to_text(for_object))
        session.process_state.dirty = True

    @staticmethod
    def abstract_objs(session):
        # Sometimes, one may need to know the list of fields which use the
        # Abstract tool on a particular object.
        #
        # TODO :
        #  - same as get_abstract_object

        res = []
        # We just need to look for the '_db' pattern in our fields
        for field in [
                field for field in dir(session.process_state)
                if field[-3:] == '_db']:
            res.append(field[:-3])
        return res

    @staticmethod
    def get_abstract_objects(session, fields):
        # This is the main entry point for accessing abstract objects.
        # It takes an object, and a list of field names to look for.
        objs = WithAbstract.abstract_objs(session)

        # We convert 'fields' to a list if needed
        elems = to_list(fields)
        res = []
        for field in elems:
            if field in objs:
                # We check that the current field exists in the object before
                # getting it !
                res.append(WithAbstract.get_abstract_object(session, field))

        if isinstance(fields, list):
            return res
        else:
            return res[0]

    @staticmethod
    def save_abstract_objects(session, fields):
        # Here we store the specified fields in the object where they have been
        # defined.
        objs = WithAbstract.abstract_objs(session)

        # We convert to a list if needed
        for_list = to_list(fields)
        for field, value in for_list:
            # Then store each element.
            if field in objs:
                WithAbstract.save_abstract_object(session, field, value)


class BadDataKeyError(Exception):
    'Bad data key error'
    # This exception will be raised when trying to access or set a non-existing
    # field of an object via the WithAbstract tool.

    pass

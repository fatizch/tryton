import ConfigParser
import os
import datetime
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool
from trytond.model import Model
from trytond.model import fields as fields
# Needed for proper encoding / decoding of objects as strings
from trytond.protocols.jsonrpc import JSONEncoder, object_hook

# Needed for serializing data
try:
    import simplejson as json
except ImportError:
    import json


def get_descendents(from_class, names_only=False):
    res = []
    if names_only:
        format_ = lambda x: x
    else:
        format_ = lambda x: (x, x)
    if isinstance(from_class, str):
        the_class = Pool().get(from_class)
        cur_models = [model_name
                      for model_name, model in Pool().iterobject()
                      if issubclass(model, the_class)]
        Model = Pool().get('ir.model')
        models = Model.search([('model', 'in', cur_models)])
        for cur_model in models:
            res.append(format_(cur_model.model))
    elif isinstance(from_class, type):
        names = [elem for elem, _ in Pool().iterobject()]
        for elem in from_class.__subclasses__():
            if isinstance(elem, type) and elem.__name__ in names:
                res.append(format_(elem.__name__))
    return res


def get_descendents_name(from_class):
    result = []
    for model_name, model in Pool().iterobject():
        if issubclass(model, from_class):
            result.append((model_name, model.__doc__.splitlines()[0]))
    return result


def get_module_name(cls):
    return cls.__name__.split('.')[0]


def change_relation_links(cls, from_module, to_module):
    for field_name in dir(cls):
        field = getattr(cls, field_name)
        attr_name = ''
        if hasattr(field, 'model_name'):
            attr_name = 'model_name'
        if hasattr(field, 'relation_name'):
            attr_name = 'relation_name'
        if attr_name == '':
            continue
        model_name = getattr(field, attr_name)
        if not (model_name.startswith(from_module)
                and model_name.split('.', 1)[0] == from_module):
            continue
        setattr(field, attr_name,
            to_module + model_name.split(from_module)[1])
        setattr(cls, field_name, field)


def to_list(data):
    if type(data) == list:
        return data
    elif type(data) == str:
        return [data]
    else:
        return [data]


class BadDataKeyError(Exception):
    'Bad data key error'
    # This exception will be raised when trying to access or set a non-existing
    # field of an object via the WithAbstract tool.

    pass


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
        elif isinstance(value, dict) and isinstance(field_desc,
                (fields.Many2One, fields.Reference)):
            # If the value is a dict and the expected field value an instance,
            # we assume that we can create it then go !
            res = WithAbstract.create_abstract(field_desc.model_name, value)
        elif isinstance(value, str) and isinstance(field_desc,
                (fields.Reference)):
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
        for field in [field for field in dir(session.process_state)
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


class NonExistingManagerException(Exception):
    pass


class GetResult(object):
    def get_result(self, target, args, manager='', path=''):
        # This method is a generic entry point for getting parameters.
        #
        # Arguments are :
        #  - The target value to compute. It is a key which will be used to
        #    decide which data is asked for
        #  - The dict of arguments which will be used by the rule to compute.
        #    Another way to do this would be a link to a method on the caller
        #    which would provide said args on demand.
        #  - The manager will usually be filled, it is a key to finding where
        #    the required data is stored. So if the target is "price", the
        #    manager should be set to "pricing".
        #  - We can use the 'path' arg to specify the way to our data.
        #    Basically, we try to match the first part of path (which looks
        #    like a '.' delimited string ('alpha1.beta3.gamma2')) to one of the
        #    sub-elements of self, then iterate.

        if path:
            # If a path is set, the data we look for is not set on self. So we
            # need to iterate on self's sub-elems.
            #
            # First of all, we need the sub-elems descriptor. This is the
            # result of the get_sub_elem_data method, which returns a tuple
            # with the field name to iterate on as the first element, and
            # this field's field on which to try to match the value.
            sub_elem_data = self.get_sub_elem_data()

            if not sub_elem_data:
                # If it does not exist, someone failed...
                return (None, ['Object %s does not have any sub_data.'
                    % (self.name)])

            path_elems = path.split('.')

            for elem in getattr(self, sub_elem_data[0]):
                # Now we iterate on the specified field
                if path_elems[0] in (getattr(elem, attr) for attr in
                        sub_elem_data[1]):
                    if isinstance(elem, GetResult):
                        return elem.get_result(target, args, manager,
                            '.'.join(path_elems[1:]))
                    return (None, ['Sub element %s of %s cannot get_result !'
                        % (elem.name, self.name)])
            return (None, ['Could not find %s sub element in %s'
                % (path_elems[0], self.name)])

        if manager:
            # A manager is specified, we look for it
            for brm_name, brm in [(elem, getattr(self, elem))
                    for elem in dir(self) if elem.endswith('_mgr')]:
                if not brm_name.startswith(manager):
                    continue
                if brm is None or len(brm) == 0:
                    break
                # When found, we just call the get_result method with our args
                try:
                    good_rule = brm[0].get_good_rule_at_date(
                        args).get_good_rule_from_kind()
                except Exception:
                    good_rule = None
                if not good_rule:
                    return (None, ['Could not find a matching manager'])
                return good_rule.get_result(target, args)
            # We did not found any manager matching the specified name
            raise NonExistingManagerException
            return  (None, ['Business Manager %s does not exist on %s'
                % (manager, self.name)]
                )

        # Now we look for our target, as it is at our level
        target_func = getattr(self, 'give_me_' + target)

        result = target_func(args)
        if not isinstance(result, tuple) and not result is None:
            return (result, [])
        return result

    def get_sub_elem_data(self):
        # Should be overridden
        return None


def add_results(results):
    # This function can be used to concatenate simple return types, of the
    # form (result, [errors]).
    # It supposes that the result's type supports the += operator
    res = [None, []]
    for cur_res in results:
        if cur_res == (None, []):
            continue
        elif cur_res[0] is None:
            res[1] += cur_res[1]
        elif res[0] is None:
            res[0] = cur_res[0]
            res[1] += cur_res[1]
        else:
            res[0] += cur_res[0]
            res[1] += cur_res[1]
    return tuple(res)


def get_data_from_dict(data, dict):
    # This is used to parse a given dict for a set of data, and returns a dict
    # and a list of errors in the case it could not find one or more of the
    # specified data keys in the dict.
    res = ({}, [])
    for elem in data:
        if elem in dict:
            res[0][elem] = dict[elem]
        else:
            res[1] += '%s data not found' % elem
    return res


def convert_ref_to_obj(ref):
    # Currently (version 2.4), tryton does not convert automatically Reference
    # fields from string concatenation to browse objects.
    # That might evolve in the future, meanwhile this litlle method should make
    # it easier to do.
    #
    # Warning : it is not failsafe
    if isinstance(ref, Model):
        return ref
    try:
        model, id = ref.split(',')
    except Exception:
        raise
    model_obj = Pool().get(model)
    return model_obj(id)


def priority(priority_lvl):
    # This function is meant to be used as a decorator that will allow the
    # definition of priorities on other functions.
    # This is especially important in the case of before / post step methods
    # in the CoopProcess framework.
    #
    # USAGE :
    #    @priority(4)
    #    def my_func...
    def wrap(f):
        f.priority = priority_lvl
        return f
    return wrap


def keywords(keys):
    def wrap(f):
        f.keywords = keys
        return f
    return wrap


def limit_dates(dates, start=None, end=None):
    res = list(dates)
    res.sort()
    final_res = []
    for elem in res:
        if (not start or elem > start) and (not end or elem <= end):
            final_res.append(elem)
    if start and (not final_res or final_res[0] and final_res[0] != start):
        final_res.insert(0, start)
    if end and final_res[-1] != end:
        final_res.append(end)
    return final_res


def to_date(string, format='ymd'):
    elems = [int(value) for value in string.split('-')]
    return datetime.date(elems[0], elems[1], elems[2])


def get_field_size(the_instance, val_name):
    field = getattr(the_instance.__class__, val_name)
    if field and hasattr(field, 'size'):
        return field.size


def tuple_index(value, the_tuple, key_index=0):
    '''
    Retrieve the index of the value in the tuple, comparing the
    value with the key_index value of the tuple'''
    return [y[key_index] for y in list(the_tuple)].index(value)


def get_module_path(module_name):
    module_path = os.path.abspath(os.path.join(os.path.normpath(__file__),
        '..', '..', module_name))
    if os.path.isdir(module_path):
        return module_path


def get_coop_config(section, option):
    coop_utils = get_module_path('coop_utils')
    if coop_utils:
        config = ConfigParser.ConfigParser()
        config.read(os.path.join(coop_utils, 'coop.cfg'))
        return config.get(section, option)


def today():
    return Pool().get('ir.date').today()


def get_good_versions_at_date(instance, var_name, at_date=None):
    '''This method looks for the elements in the list which are effective at
    the date. By default, it will check that the at_date is between the start
    date and the end_date, otherwise it will check if there is already a
    specific method on the object'''

    if not at_date:
        at_date = today()
    if hasattr(instance, 'get_good_versions_at_date'):
        return getattr(instance, 'get_good_versions_at_date')(var_name,
            at_date)
    res = []
    element_added = False
    for element in reversed(getattr(instance, var_name)):
        if (not hasattr(element, 'end_date')
            and hasattr(element, 'start_date)')):
            if not element.start_date:
                res.insert(0, element)
            elif at_date >= element.start_date and not element_added:
                res.insert(0, element)
                element_added = True
        elif hasattr(element, 'start_date') and hasattr(element, 'end_date'):
            if (not element.start_date or at_date >= element.start_date) and (
                not element.end_date or at_date <= element.end_date):
                res.insert(0, element)
        else:
            res.insert(0, element)
    return res


def get_good_version_at_date(instance, var_name, at_date=None):
    res = get_good_versions_at_date(instance, var_name, at_date)
    if len(res) == 1:
        return res[0]


def add_frequency(frequency, to_date):
    if frequency == 'yearly':
        return to_date + relativedelta(years=+1)
    elif frequency == 'half-yearly':
        return to_date + relativedelta(months=+6)
    elif frequency == 'quarterly':
        return to_date + relativedelta(months=+3)
    elif frequency == 'monthly':
        return to_date + relativedelta(months=+1)


def get_those_objects(model_name, domain, limit=None):
    the_model = Pool().get(model_name)
    return the_model.search(domain, limit=limit)


def delete_reference_backref(objs, target_model, target_field):
    the_model = Pool().get(target_model)
    to_delete = the_model.search([(
        target_field, 'in', [
            '%s,%s' % (obj.__name__, obj.id)
            for obj in objs])])
    the_model.delete(to_delete)

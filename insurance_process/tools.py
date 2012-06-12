# Needed for getting models
from trytond.pool import Pool

# Needed for fields
from trytond.model import fields as fields
from trytond.model import Model
from trytond.wizard import Wizard

# Needed for data storage
from trytond.protocols.jsonrpc import JSONEncoder

# Needed for serializing data
try:
    import simplejson as json
except ImportError:
    import json


def to_list(data):
    if type(data) == list:
        return data
    elif type(data) == str:
        return [data]
    else:
        return [data]


class AbstractObject(object):
    '''
        This class is designed as to provide an abstract way to access to
        data, whether it is stored in the database or still a dictionnary.
    '''

    def __init__(self, model_name, for_id=0, init_data=None):
        # Whatever the status of the object (stored or not yet), it has a
        # model name, which describes it.
        #
        # NOTE : we need to bypass the getattr method as it is overriden, so
        # we set the field through direct access.
        self.__dict__['_model_name'] = model_name

        # If the object already exists in the database, it got an id so we
        # need to store it for later use.
        self.__dict__['_id'] = for_id

        # This structure will be a dictionnary where the key are the names
        # of the fields of the object.
        _attrs = {}

        if init_data is None:
            init_dict = {}
        elif type(init_data) in (Wizard):
            init_dict = init_data._data
        elif type(init_data) in (dict,):
            init_dict = init_data
        else:
            init_dict = {}

        # If the object DOES NOT exist yet, we will need to create a basic
        # datastructure which will be used to store and access data
        if for_id <= 0:

            # In order to provide the right fields, we need to get them from
            # the model.
            try:
                model_obj = Pool().get(model_name)
            except:
                model_obj = None
            if not model_obj is None:
                # So we go through all the attributes which are part of the
                # model and which are fields as in tryton field
                for (field_name, field) in [(field, getattr(model_obj, field))
                              for field in dir(model_obj)
                              if (isinstance(getattr(model_obj, field),
                                            fields.Field)
                                  and not field in ('create_uid',
                                                         'create_date',
                                                         'write_uid',
                                                         'write_date',
                                                         'id'))]:
                    # If said field is a list, so shall it be
                    if (isinstance(field, fields.One2Many)
                            or isinstance(field, fields.Many2Many)):
                        _attrs[field_name] = []
                    # else, we just need to create the key, to avoid KeyErrors
                    # when accessing.
                    else:
                        _attrs[field_name] = None

            for field_name in init_dict.keys():
                if field_name in _attrs:
                    init_value = init_dict[field_name]
                    if type(init_value) in (Model, AbstractObject):
                        _attrs[field_name] = init_value
                    elif type(init_value) in (dict,):
                        _attrs[field_name] = AbstractObject(
                                                    getattr(model_obj,
                                                    field_name).model_name,
                                                    init_data=init_value)
                    elif type(init_value) in (list,):
                        for elem in init_value:
                            _attrs[field_name].append(AbstractObject(
                                                    getattr(model_obj,
                                                    field_name).model_name,
                                                    init_data=elem))
                    elif type(getattr(model_obj,
                                      field_name)) in (fields.Many2One,):
                        if type(init_value) in (int, long):
                            _attrs[field_name] = AbstractObject(
                                                    getattr(model_obj,
                                                    field_name).model_name,
                                                    init_value)
                    else:
                        _attrs[field_name] = init_value

        # And finally we set up the _attrs field.
        self.__dict__['_attrs'] = _attrs

    def get_model_fields(self):
        try:
            model_obj = Pool().get(self._model_name)
        except:
            model_obj = None
        if not model_obj is None:
            return [(field, getattr(model_obj, field))
                    for field in dir(model_obj)
                    if (isinstance(getattr(model_obj, field), fields.Field)
                            and not field in ('create_uid',
                                              'create_date',
                                              'write_uid',
                                              'write_date',
                                              'id'))]
        return []

    # Now we override the __getattr__ method so that we look in the _attrs dict
    # for keys matching the asked field name.
    def __getattr__(self, name):
        # First of all, if the field is a native field, no need to go further
        if name in self.__dict__:
            return self.__dict__[name]
        # Otherwise there are two possibilities :
        elif self._id <= 0:
            # If we are talking of non-yet stored object
            if name in self._attrs:
                # We just return the value that is in the dictionnary.
                return self._attrs[name]
            else:
                raise KeyError
        else:
            # If self is a stored object, we return the fields value as
            # a BrowseRecord value :
            obj = Pool().get(self._model_name)
            return obj.browse(self._id).name

    # This method will be use to create an AbstractObject from a value,
    # whatever the value type.
    def create_abstract(self, model, value):
        if isinstance(value, AbstractObject):
            # It is already an abstract object, we just need to check
            # that we got the model right
            if value._model_name == model:
                return value
            else:
                raise TypeError
        elif isinstance(value, (int, long)):
            # It is an id, we create the object and specify it
            return AbstractObject(model, id=value)
        elif isinstance(value, Model):
            # It is a BrowseRecord, we create the AbstractObject.
            if value._model._name == model:
                return AbstractObject(value._model._name, value.id)
            else:
                raise TypeError
        else:
            raise TypeError
        # Anything else is an error...

    # We need a way to set values on our object
    def __setattr__(self, name, value):
        if name in self.__dict__:
        # Again, no need to make it complicated if the value is meant for a
        # native field of self.
            self.__dict__[name] = value
        elif self._id <= 0 and name in self._attrs:
            # If we are working with a dict and that the field name exists in
            # it (as we created the dict structure from the model, it means
            # that the field also exists in the model)
            obj = Pool().get(self._model_name)
            field = getattr(obj, name)

            # We need some special handling for list types
            if isinstance(field, fields.One2Many):
                # When setting a One2Many list, we expect an abstract object
                # for each element of the list
                if type(value) == list:
                    for elem in value:
                        if (type(elem) in (Model,) and
                                    elem._model._name == field.model_name):
                            self._attrs[name].append(
                                AbstractObject(elem._model._name, elem.id))
                        elif type(elem) in (AbstractObject,):
                            self._attrs[name].append(elem)
                        else:
                            raise TypeError
                else:
                    # Anything else raises an error
                    raise TypeError
            elif isinstance(field, fields.Many2Many):
                # For Many2Many fields, objects might be AbstractObjects, ids,
                # BroqseRecords, etc...
                if type(value) == list:
                    self._attrs[name] = []
                    for elem in value:
                        # So we use the create_abstract method to return an
                        # abstract object which encapsulates the data.
                        self._attrs[name].append(
                                self.create_abstract(field.model_name, elem))
                else:
                    raise TypeError
            elif isinstance(field, fields.Many2One):
                # in case of a Many2One, we cannot know the value type as well,
                # the create_abstract method will do the work for us.
                self._attrs[name] = self.create_abstract(field.model_name,
                                                         value)
            else:
                # Anything else is (hopefully) a basic type, so we just set
                # the value.
                self._attrs[name] = value
        elif self._id != 0:
            # This should not be commonly used, as it requires a manual save of
            # the object later.
            obj = Pool().get(self._model_name)
            obj.browse(self._id).__setattr__(name, value)
        else:
            raise KeyError

    @staticmethod
    def load_from_dict(res):
        abstract = AbstractObject(res['abstract_model_name'], res['id'])
        attrs = {}
        for elem in res['attrs']:
            value = res['attrs'][elem]
            if value is None:
                attrs[elem] = None
            elif isinstance(value, dict) and 'abstract_model_name' in value:
                attrs[elem] = AbstractObject.load_from_dict(
                                                        res['attrs'][elem])
            elif isinstance(value, list):
                attrs[elem] = []
                for obj in value:
                    if isinstance(obj, dict) and 'abstract_model_name' in obj:
                        attrs[elem].append(AbstractObject.load_from_dict(obj))
            else:
                attrs[elem] = res['attrs'][elem]
        abstract.__dict__['_attrs'] = attrs
        return abstract

    @staticmethod
    def load_from_text(text):
        # This will take a json text as an input and create the corresponding
        # abstract object
        if not (text is None or text == ''):
            res = json.loads(text.encode('utf-8'))
            return AbstractObject.load_from_dict(res)
        else:
            return None

    @staticmethod
    def storable_dict(for_object):
        storable_attrs = {}
        for field in for_object._attrs:
            value = for_object._attrs[field]
            if value is None:
                storable_attrs[field] = None
            elif isinstance(value, AbstractObject):
                storable_attrs[field] = AbstractObject.storable_dict(value)
            elif isinstance(value, Model):
                storable_attrs[field] = AbstractObject.storable_dict(
                                          AbstractObject(value._model._name,
                                                         value.id))
            elif isinstance(value, list):
                storable_list = []
                for elem in value:
                    if type(elem) in (AbstractObject,):
                        storable_list.append(
                                        AbstractObject.storable_dict(elem))
                    elif type(value) in (Model,):
                        storable_list.append(AbstractObject.storable_dict(
                                          AbstractObject(elem._model._name,
                                                         elem.id)))
                    else:
                        storable_list.append(elem)
                storable_attrs[field] = storable_list
            else:
                storable_attrs[field] = json.dumps(value, cls=JSONEncoder)
        return {'abstract_model_name': for_object._model_name,
                'id': for_object._id,
                'attrs': storable_attrs}

    @staticmethod
    def store_to_text(for_object):
        return json.dumps(AbstractObject.storable_dict(for_object),
                          cls=JSONEncoder)

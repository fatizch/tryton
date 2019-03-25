# encoding: utf8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import csv
import re
import unicodedata

from collections import namedtuple
from decimal import Decimal

from trytond.config import config
from trytond.pool import Pool
from trytond.modules.coog_core import utils


class DSNValidationError(Exception):
    pass


class Entry(namedtuple("DSNEntry", ['id_', 'value'])):

    def __str__(self):
        # prepare for python3
        return ','.join([self.id_, "'%s'" % self.value])

    def __unicode__(self):
        return ','.join([self.id_, "'%s'" % self.value])


class NEODeSTemplate(utils.DataExporter):
    encoding = 'iso-8859-1'
    custom_mapping = None
    mapping = {
        # Dispatch block
        'S10.G00.00.001': 'software_name',
        'S10.G00.00.002': 'software_editor_name',
        'S10.G00.00.003': 'software_version_number',
        # 'S10.G00.00.004':
        'S10.G00.00.005': 'dispatch_test_code',
        'S10.G00.00.006': 'norm_version',
        'S10.G00.00.008': 'dispatch_kind',

        # Sender block
        'S10.G00.01.001': 'siren',
        'S10.G00.01.002': 'conf_sender_nic',
        'S10.G00.01.003': 'name',
        'S10.G00.01.004': 'main_address_street',
        'S10.G00.01.005': 'main_address.zip',
        'S10.G00.01.006': 'main_address.city',
        'S10.G00.01.007': 'main_address_country_code',

        # 'S10.G00.01.008': 'main_address.?',
        # 'S10.G00.01.009': 'main_address.?',
        # 'S10.G00.01.010': 'main_address.?',

        # Sender contact block
        'S10.G00.02.001': 'conf_sender_contact_civility',
        'S10.G00.02.002': 'conf_sender_contact_full_name',
        'S10.G00.02.004': 'conf_sender_contact_email',
        'S10.G00.02.005': 'conf_sender_contact_phone',

        # Declaration block
        'S20.G00.05.001': 'declaration_nature',
        'S20.G00.05.002': 'declaration_kind',
        'S20.G00.05.003': 'conf_fraction_number',
        'S20.G00.05.004': 'declaration_rank',
        'S20.G00.05.005': 'declaration_month',
        'S20.G00.05.007': 'file_date',
        # 'S20.G00.05.009': '',  #   Identifiant métier
        'S20.G00.05.010': 'declaration_currency',

        # Footer : totals
        'S90.G00.90.001': 'total_entries',  # len(message) + 2
        'S90.G00.90.002': 'declaration_number',  # Nombre de déclarations
    }

    def __init__(self, origin, testing=False, void=False, replace=False):
        self.origin = origin
        self.void = void
        self.replace = replace
        self.load_specifications()
        self.errors = []
        self.message = []
        conf_testing = config.get('dsn', 'testing')
        if conf_testing:
            self.testing = conf_testing == 'True'
        else:
            self.testing = testing
        if self.custom_mapping:
            self.mapping.update(self.custom_mapping)

    def load_specifications(self):
        self.spec = NEODES()

    def format_amount(self, amount):
        return '%s' % str(amount.quantize(Decimal(10) ** -2))

    def format_date(self, date):
        return '%s' % date.strftime('%d%m%Y')

    def generate(self):
        self._generate()
        self.validate()
        # We must add a \n at the end because the specifications
        # says that every line must end with a '0A' byte
        return ('\n'.join([str(x) for x in self.message]) + '\n').encode(
            'latin1')

    def _generate(self):
        for structure in ('S10', 'S20', 'S90'):
            self.generate_structure(structure)

    def generate_structure(self, structure_name):
        # header here is whole block id, eg: S10.G00.02
        headers = [x for x in list(self.spec.header_defs.keys())
            if x.startswith(structure_name)]
        self.generate_message(headers)

    def generate_message(self, blocks_ids, parent=None):
        for block_id in blocks_ids:
            child_block_ids = self.get_child_block_ids(block_id)
            for instance in self.get_instances(block_id, parent):
                self.generate_block_message(instance, block_id, parent)
                if child_block_ids:
                    self.generate_message(child_block_ids, instance)

    def get_child_block_ids(self, parent_id):
        return sorted([k for k, v in self.spec.block_defs.items()
                if v['ParentId'] == parent_id])

    def generate_block_message(self, instance, block_id, parent):
        field_defs = self.get_field_defs(block_id)
        for field_def in field_defs:
            val = self.get_value(instance, field_def, parent)
            if val == -1 or val is None:
                continue
            val = self.dsn_field_format(val, field_def)
            assert val and isinstance(val, type('')), (
                'Value of %s is %s , type %s' % (field_def[0], val, type(val)))
            self.message.append(Entry(field_def[0], val))

    def get_field_defs(self, block_id):
        return sorted([(k, v) for k, v in self.spec.field_defs.items()
            if k.startswith(block_id)], key=lambda x: x[0])

    def get_value(self, instance, field_def, parent):
        if field_def[0] in self.mapping:
            name = self.mapping[field_def[0]]
            if name.startswith('conf_'):
                return self.get_conf_item(name[5:])
            return self.instance_field_getter(instance, name)
        # ignore undefined fields
        return -1

    def ascii_alpha_num(self, value):
        # Normalize to NFKD, then ignore non ascii,
        # which converts accented to non accented.
        # Then remove all non alphanumeric characters
        return re.sub(r'[\W_]+', ' ',
            unicodedata.normalize('NFKD', value).encode(
                'ascii', 'ignore').decode('ascii')).strip()

    def dsn_field_format(self, val, field_def):
        formats = {
            'N4DS_Adresse_Localite': self.ascii_alpha_num
            }
        formatting = formats.get(field_def[1]['DataType Id'])
        if formatting:
            val = formatting(val)
        return val

    def validate(self):
        for entry in self.message:
            # TODO : check for fordidden chars
            self.check_value(entry)
            self.check_encodable(entry)
        if self.errors:
            concat = "\n".join(self.errors)
            raise DSNValidationError(("\n" + concat).encode('utf8'))
        return True

    def check_encodable(self, entry):
        try:
            str(entry).encode('latin1')
        except UnicodeEncodeError:
            raise DSNValidationError(
                'Cannot encode %s to latin1' % str(entry).encode('utf8'))

    def check_value(self, entry):
        field_def = self.spec.field_defs[entry.id_]
        data_def = self.spec.data_types[field_def["DataType Id"]]
        self.check_regexp(entry, data_def, field_def)
        self.check_length(entry, data_def, field_def)

    def check_regexp(self, entry, data_def, field_def):
        exp = data_def.get("CompiledRegex")
        if exp:
            match = exp.fullmatch(entry.value)
            if not match:
                msg = (("The value \"%s\" for entry \"%s\" (%s) does "
                "not match regexp \"%s\". The DataType is \"%s\".") % (
                    entry.value, entry.id_, field_def["Comment"],
                    data_def['Regexp'], data_def['Name']))
                self.errors.append(msg)

    def check_length(self, entry, data_def, field_def):
        min_length = int(data_def['Lg Min'])
        max_length = int(data_def['Lg Max'])
        len_ = len(entry.value)
        valid_ = (len_ >= min_length) and (len_ <= max_length)
        if not valid_:
            msg = (("The value \"%s\" for entry \"%s\" (%s) , length %s does "
            "not match Min Length \"%s\" or Max Length \"%s\" ."
            "The DataType is \"%s\".") % (
                entry.value, entry.id_, field_def["Comment"],
                str(len_), data_def['Lg Min'],
                data_def['Lg Max'], data_def['Name']))
            self.errors.append(msg)

    def get_instances(self, block_id, parent):
        Party = Pool().get('party.party')
        if block_id == 'S10.G00.00':
            return [self]
        elif block_id == 'S10.G00.01':  # sender
            sender_code = self.get_conf_item('sender_code')
            sender, = Party.search(['code', '=', sender_code])
            return [sender]
        elif block_id == 'S10.G00.02':  # sender contact
            return [self]
        elif block_id == 'S20.G00.05':  # Declaration
            return [self]
        elif block_id == 'S90.G00.90':  # totals
            return [self]
        return []

    @property
    def software_name(self):
        return 'Coog'

    @property
    def software_editor_name(self):
        return 'Coopengo'

    @property
    def software_version_number(self):
        from trytond.modules import get_module_info
        return get_module_info('dsn_standard').get('version')

    @property
    def dispatch_kind(self):
        return '01' if not self.void else '02'

    @property
    def dispatch_test_code(self):
        return '01' if self.testing else '02'  # sic!

    @property
    def norm_version(self):
        return '201710'  # not sure

    def get_conf_item(self, item):
        conf_item = config.get('dsn', item)
        assert conf_item, "Please set %s in the dsn section of "\
            "the configuration" % item
        return str(config.get('dsn', item))

    @property
    def declaration_nature(self):
        if config.getboolean('env', 'testing') is True:
            return '21'
        raise NotImplementedError

    @property
    def declaration_kind(self):
        if not self.replace:
            return '01' if not self.void else '02'
        return '03' if not self.void else '05'

    @property
    def declaration_rank(self):
        if config.getboolean('env', 'testing') is True:
            return '24'
        raise NotImplementedError

    @property
    def declaration_month(self):
        if config.getboolean('env', 'testing') is True:
            return str(utils.today().strftime('01%m%Y'))
        raise NotImplementedError

    @property
    def file_date(self):
        return str(utils.today().strftime('%d%m%Y'))

    @property
    def declaration_currency(self):
        return '01'

    @property
    def total_entries(self):
        return '%s' % (len(self.message) + 2)

    @property
    def declaration_number(self):
        return '1'

    def custom_main_address_street(self, party):
        if not party.main_address:
            return u''
        else:
            return party.main_address.street.splitlines()[-1][:50]

    def custom_main_address_country_code(self, party):
        # if S10.G00.01.005 defined country must be empty
        if party.main_address.zip:
            return None
        return party.main_address.country.code


class NEODES(object):

    def __init__(self):
        self.load_field_definitions()

    def get_resource_path(self, kind):
        import sys
        fname = self.get_resource_file_name(kind)
        mpath = sys.modules[self.__module__].__file__
        return os.path.join(os.path.dirname(mpath),
            'resources/%s' % fname)

    def get_resource_file_name(self, kind):
        # The files below are the "Fields", "Data Types", "Blocks" tab from
        # http://dsn-info.custhelp.com/app/answers/detail/a_id/907/kw/datatypes
        # encoding is utf8
        return 'dsn-datatypes-CT2019-1_%s.csv' % kind

    def load_field_definitions(self):
        # fields
        # Block Id       Id      Name    Description     DataType Id    Comment
        # data types
        # Id     Name    Description     Nature  Regexp  Lg Min  Lg Max  Values
        field_defs = {}
        data_types = {}
        block_defs = {}
        header_defs = {}

        for name in ('datatypes', 'fields', 'blocks', 'headers'):
            with open(self.get_resource_path(name)) as f:
                reader = csv.DictReader(f, delimiter=';', quotechar='"')
                for row in reader:
                    if name == 'datatypes':
                        id_ = row.pop("Id")
                        data_types[id_] = row
                        reg = data_types[id_]["Regexp"]
                        if reg:
                            data_types[id_]["CompiledRegex"] = re.compile(reg)
                    elif name == 'fields':
                        id_ = '.'.join([row.pop("Block Id"), row.pop("Id")])
                        field_defs[id_] = row
                    elif name == 'blocks':
                        id_ = row.pop("Id")
                        block_defs[id_] = row
                    elif name == 'headers':
                        id_ = row.pop("Id")
                        header_defs[id_] = row

        self.field_defs = field_defs
        self.data_types = data_types
        self.block_defs = block_defs
        self.header_defs = header_defs

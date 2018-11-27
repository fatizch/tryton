# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.operators import NotIn

from trytond import backend
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.cache import Cache

from trytond.modules.coog_core import model, fields
from trytond.modules.coog_core import coog_string
from trytond.modules.offered.extra_data import with_extra_data_def


__all__ = [
    'Product',
    'ItemDescription',
    'ItemDescSubItemDescRelation',
    'ItemDescriptionExtraDataRelation',
    'CoveredElementEndReason',
    'ItemDescriptionEndReasonRelation',
    'ExtraData',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    item_descriptors = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Item Descriptions'),
        'on_change_with_item_descriptors')

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        return ['contract', 'covered_element', 'option']

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.extra_data_def.domain = [
            ('kind', 'in', cls.kind_list_for_extra_data_domain())]
        cls._error_messages.update({
                'missing_covered_element_extra_data': 'The following covered '
                'element extra data should be set on the product: %s',
                })

    @classmethod
    def validate(cls, instances):
        super(Product, cls).validate(instances)
        cls.validate_covered_element_extra_data(instances)

    @classmethod
    def validate_covered_element_extra_data(cls, instances):
        for instance in instances:
            from_option = set(extra_data for coverage in instance.coverages
                for extra_data in coverage.extra_data_def
                if extra_data.kind == 'covered_element')
            remaining = from_option - set(instance.extra_data_def)
            if remaining:
                instance.raise_user_error('missing_covered_element_extra_data',
                    (', '.join((extra_data.string
                                for extra_data in remaining))))

    @fields.depends('coverages')
    def on_change_with_item_descriptors(self, name=None):
        res = set()
        for coverage in self.coverages:
            if getattr(coverage, 'item_desc', None):
                res.add(coverage.item_desc.id)
        return list(res)


class ItemDescription(model.CoogSQL, model.CoogView, with_extra_data_def(
            'offered.item.description-extra_data', 'item_desc',
            'covered_element'), model.TaggedMixin):
    'Item Description'

    __name__ = 'offered.item.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    kind = fields.Selection([
            ('', ''),
            ('party', 'Party'),
            ('person', 'Person'),
            ('company', 'Company'),
            ], 'Kind')
    kind_string = kind.translated('kind')
    sub_item_descs = fields.Many2Many(
        'offered.item.description-sub_item.description',
        'item_desc', 'sub_item_desc', 'Sub Item Descriptions',
        states={'invisible': Eval('kind') == 'person'})
    coverages = fields.One2Many('offered.option.description', 'item_desc',
        'Coverages', target_not_required=True)
    covered_element_end_reasons = fields.Many2Many(
        'offered.item.description-covered_element.end_reason', 'item_desc',
        'reason', 'Possible End Reasons')
    _check_sub_options_cache = Cache('has_sub_options')
    extra_data_rec_name = fields.Selection(
        'getter_extra_data_rec_name', 'Extra Data To Show In The Rec Name',
        help='If set, the extra data value will be showed in the rec name '
        'of the covered element')
    show_name = fields.Boolean('Show Covered Element Name',
        help='If checked, the name will be showed on the covered element, '
        'allowing the editing of the field')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        # Migration from 2.0: Add show_name field
        migrate_show_name = False
        migrate_show_name = not table.column_exist('show_name')
        super(ItemDescription, cls).__register__(module_name)

        if migrate_show_name:
            item_desc = Pool().get('offered.item.description').__table__()
            cursor = Transaction().connection.cursor()
            selection = item_desc.select(item_desc.id,
                where=(item_desc.kind != Null))
            cursor.execute(*item_desc.update(
                    columns=[item_desc.show_name],
                    values=[True],
                    where=item_desc.id.in_(selection))
                )
            cursor.execute(*item_desc.update(
                    columns=[item_desc.show_name],
                    values=[False],
                    where=NotIn(item_desc.id, selection))
                )

    @classmethod
    def copy(cls, items, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('coverages', None)
        return super(ItemDescription, cls).copy(items, default=default)

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coog_string.slugify(self.name)

    @classmethod
    def _export_skips(cls):
        result = super(ItemDescription, cls)._export_skips()
        result.add('coverages')
        return result

    @classmethod
    def _export_light(cls):
        return super(ItemDescription, cls)._export_light() | {'tags'}

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('extra_data_def')
    def getter_extra_data_rec_name(self):
        return [('', '')] + [(x.name, x.string) for x in self.extra_data_def]

    def has_sub_options(self):
        cached = self.__class__._check_sub_options_cache.get(self.id, -1)
        if cached != -1:
            return cached
        value = any(x.coverages for x in self.sub_item_descs)
        self.__class__._check_sub_options_cache.set(self.id, value)
        return value


class ItemDescSubItemDescRelation(model.CoogSQL):
    'Relation between Item Desc and Sub Item Desc'

    __name__ = 'offered.item.description-sub_item.description'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE')
    sub_item_desc = fields.Many2One('offered.item.description',
        'Sub Item Desc', ondelete='RESTRICT')


class ItemDescriptionExtraDataRelation(model.CoogSQL):
    'Item Description to Extra Data Relation'

    __name__ = 'offered.item.description-extra_data'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT', )


class CoveredElementEndReason(model.CoogSQL, model.CoogView,
        model.TaggedMixin):
    'End reasons for covered elements'

    __name__ = 'covered_element.end_reason'
    _func_key = 'code'
    _rec_name = 'name'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    item_descs = fields.Many2Many(
        'offered.item.description-covered_element.end_reason',
        'reason', 'item_desc', 'Item Descriptions')

    @classmethod
    def _export_skips(cls):
        return super(CoveredElementEndReason, cls)._export_skips() | {
            'item_descs'}

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coog_string.slugify(self.name)


class ItemDescriptionEndReasonRelation(model.CoogSQL):
    'Item Description to Covered Element End Reason relation'

    __name__ = 'offered.item.description-covered_element.end_reason'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE', select=True, required=True)
    reason = fields.Many2One('covered_element.end_reason', 'End Reason',
        ondelete='RESTRICT', select=True, required=True)


class ExtraData(metaclass=PoolMeta):
    __name__ = 'extra_data'

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls._hardcoded_rule_context_matches = {
            'covered_element': [
                ('elem', ['find_extra_data_value']),
                ('subscriber', ['find_extra_data_value']),
                ],
            }

    @classmethod
    def _extra_data_value_for_rule(cls, name, context):
        if 'extra_data' in context and name in context['extra_data']:
            return context['extra_data'][name]
        data = cls._extra_data_struct(name)
        targets = []
        if data['kind'] in cls._hardcoded_rule_context_matches:
            for match_key, match_method in \
                    cls._hardcoded_rule_context_matches[data['kind']]:
                if match_key in context:
                    targets.append((context[match_key], match_method))
        if not targets:
            providers = cls._extra_data_providers[data['kind']]
            for k, v in context.items():
                if getattr(v, '__name__', None) in providers:
                    targets.append((v, providers[v.__name__]))
        for target, finders in targets:
            for finder in finders:
                try:
                    return getattr(target, finder)(name,
                        date=context.get('date', None))
                except KeyError:
                    pass
        return None

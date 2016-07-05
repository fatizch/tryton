# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import math

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button
from trytond.model import fields as tryton_fields
from trytond.pyson import Eval, Equal
from trytond.tools import cursor_dict

from sql import Desc
from sql.conditionals import Coalesce
from sql.aggregate import Count

from coop_string import translate_value, translate_label

import model
import fields

# CHANGELOG
# 11/04/2016 - Changed method name _export_diff() to _diff_skip()


LOG = logging.getLogger(__name__)


__all__ = [
    'RevisionBlame',
    'RevisionBlameWizard',
    'RevisionFormatTranslator'
    ]


class Difference(object):
    '''Represents a difference between values in two Revisions.'''
    def __init__(self, fname, ftype, base_value, other_value, instance):
        self._fname = translate_label(instance, fname)
        self._ftype = ftype
        self._base_value = base_value
        self._other_value = other_value


class DifferenceTarget(object):
    def __init__(self, fname, target_recname, target_diffs, instance):
        self.fname = translate_label(instance, fname)
        # self.ftype = ftype
        self.target_name = target_recname
        self.diffs = target_diffs


class DifferenceAdded(Difference):
    '''Represents a difference that was added to a Revision.'''
    def __init__(self, fname, ftype, new_value, instance):
        super(DifferenceAdded, self).__init__(
            fname, ftype, new_value, None, instance)


class DifferenceRemoved(Difference):
    '''Represents a difference that was removed to a Revision.'''
    def __init__(self, fname, ftype, old_value, instance):
        super(DifferenceRemoved, self).__init__(
            fname, ftype, old_value, None, instance)


class Formatter(object):

    @staticmethod
    def newline(content):
        return u'<div>{}</div>'.format(content)

    @staticmethod
    def strong(content):
        return u'<b>{}</b>'.format(content)

    @staticmethod
    def color(content, color='blue'):
        if color not in ['red', 'green', 'blue']:
            return content
        return u"<font color='{}'>{}</font>".format(color, content)

    @staticmethod
    def indent(content, n=4):
        return (' ' * n) + content

    @staticmethod
    def header(revision):
        placeholder = u'#+ {0:<{align}}: {1}'
        label = translate_label(
            RevisionFormatTranslator(), 'author_label')
        author = placeholder.format(label, revision.create_user(), align=17)
        date = placeholder.format('DATE', revision.create_date(), align=22)
        return [Formatter.newline(('=' * 60)),
            Formatter.newline(Formatter.strong(author)),
            Formatter.newline(Formatter.strong(date)),
            Formatter.newline(('=' * 60))
            ]

    @staticmethod
    def format(diff_obj):
        placeholder = u'|   {}: {} \u2192 {}'
        bvalue = Formatter.color(diff_obj._base_value)
        ovalue = Formatter.color(diff_obj._other_value)
        return Formatter.newline(
            placeholder.format(diff_obj._fname, ovalue, bvalue))

    @staticmethod
    def format_target(difference):
        lines = []
        subheader = u'@{} = [ {} : {} ]'
        label = translate_label(
            RevisionFormatTranslator(), 'target_label')
        header = subheader.format(label,
            difference.fname, difference.target_name)
        lines.append(Formatter.newline(Formatter.strong(
                Formatter.indent(header))))
        placeholder = u'| {:<{justify}}: {} \u2192 {}'
        for diff in difference.diffs:
            bvalue = Formatter.color(diff._base_value, 'blue')
            ovalue = Formatter.color(diff._other_value, 'blue')
            diff_str = placeholder.format(diff._fname,
                ovalue, bvalue, justify=30 - len(diff._fname))
            lines.append(Formatter.newline(Formatter.indent(diff_str)))
        lines.append(Formatter.newline(''))
        return lines

    @staticmethod
    def format_added(difference):
        placeholder = u'| + {}: {}'
        value = Formatter.color(difference._base_value, 'green')
        return Formatter.newline(
            placeholder.format(difference._fname, value))

    @staticmethod
    def format_removed(difference):
        placeholder = u'| - {}: {}'
        value = Formatter.color(difference._base_value, 'red')
        return Formatter.newline(
            placeholder.format(difference._fname, value))


class Revision(object):

    def __init__(self, model_name, info):
        self._Model = Pool().get(model_name)
        if 'instance' in info:
            self._instance = info['instance']
            self._create_uid = self._instance.write_uid
            self._create_date = self._instance.write_date
        else:
            self._create_uid = info['create_uid']
            self._create_date = info['create_date']
            with Transaction().set_context(_datetime=self._create_date):
                self._instance = self._Model(info['id'])

    def fields(self, type_excludes):
        return self._exclude(self._Model._fields, type_excludes)

    def __getattr__(self, key):
        return getattr(self._instance, key)

    def _exclude(self, fields, type_excludes):
        filtered = {}
        for k, v in fields.iteritems():
            if isinstance(v, tuple(type_excludes)):
                continue
            elif k in self._Model._diff_skip():
                continue
            filtered[k] = v
        return filtered.iteritems()

    def create_user(self):
        Model = Pool().get('res.user')
        return Model(self._create_uid).name

    def create_date(self):
        Date = Pool().get('ir.date')
        return Date.datetime_as_string(self._instance.write_date)


class Revisions(object):

    def __init__(self, instance, current_page, total_pages, per_page):
        self._instance = instance
        history = self._instance.__table_history__()
        cursor = Transaction().connection.cursor()
        # select create_uid to retrieve a username
        # select create date so we can find the right revision
        cursor.execute(*history.select(
                history.id,
                Coalesce(history.write_uid,
                         history.create_uid).as_('create_uid'),
                Coalesce(history.write_date,
                         history.create_date).as_('create_date'),
                where=(history.id == instance.id),
                order_by=Desc(Coalesce(history.write_date,
                        history.create_date)),
                limit=per_page,
                offset=((current_page - 1) * per_page)
                ))
        self._revisions = list(cursor_dict(cursor))
        self._index = 0

    def __iter__(self):
        return self

    def __len__(self):
        return len(self._revisions)

    def next(self):
        try:
            base = Revision(
                self._instance.__name__,
                self._revisions[self._index])
            other = Revision(
                self._instance.__name__,
                self._revisions[self._index + 1])
        except IndexError:
            raise StopIteration
        except Exception:
            LOG.error('An error occured while iterating revisions.')
            raise StopIteration
        else:
            self._index += 1
            return (base, other)


def difference(base, other, type_excludes=None):
    dlist = []
    if type_excludes is None:
        type_excludes = [tryton_fields.Function]
    if base is None or other is None:
        return dlist
    for fname, field in base.fields(type_excludes):
        base_value = getattr(base, fname)
        other_value = getattr(other, fname)
        if isinstance(field, tryton_fields.One2Many):
            exclude = [  # set excludes for recursive call
                tryton_fields.Function,
                tryton_fields.One2Many,
                tryton_fields.Many2Many,
                ]
            for b in set(base_value):
                try:
                    o = other_value[other_value.index(b)]
                except:
                    added = DifferenceAdded(fname,
                        field, b.rec_name, base._instance)
                    dlist.append(added)
                else:
                    target_base = Revision(b.__name__, {'instance': b})
                    target_other = Revision(o.__name__, {'instance': o})
                    target_dlist = difference(target_base,
                                              target_other, exclude)
                    if len(target_dlist) > 0:
                        target_diff = DifferenceTarget(fname,
                            target_base.rec_name, target_dlist,
                            base._instance)
                        dlist.append(target_diff)
            for o in set(other_value):
                try:
                    base_value[base_value.index(o)]
                except:
                    dlist.append(DifferenceRemoved(
                             fname, field, o.rec_name, base._instance))
        elif isinstance(field, tryton_fields.Many2Many):
            for item in set(base_value) ^ set(other_value):
                if item not in other_value:  # item was added
                    item_diff = DifferenceAdded(fname, field,
                        item.rec_name, base._instance)
                    dlist.append(item_diff)
                elif item not in base_value:  # item was removed
                    item_diff = DifferenceRemoved(fname, field,
                        item.rec_name, other._instance)
                    dlist.append(item_diff)
        else:
            if base_value != other_value:
                if (isinstance(field, (fields.Date,
                            fields.Dict, fields.Selection))):
                    if base_value:
                        base_value = translate_value(base._instance, fname)
                    if other_value:
                        other_value = translate_value(other._instance, fname)
                elif isinstance(field, tryton_fields.Many2One):
                    if base_value:
                        base_value = base_value.rec_name
                    if other_value:
                        other_value = other_value.rec_name
                dlist.append(Difference(fname, field, base_value,
                        other_value, base._instance))
    return dlist


def generate_diff(instance, current_page, total_pages, per_page=10):
    '''Loops through every Revision belonging to the passed model_id and
    generate a text summary of differeneces similiary to Git.
    '''
    lines = []
    for base, other in Revisions(instance, current_page, total_pages,
            per_page):
        difflist = difference(base, other)
        if len(difflist) > 0:
            lines += Formatter.header(base)
            for diff in difflist:
                if isinstance(diff, DifferenceTarget):
                    lines += Formatter.format_target(diff)
                elif isinstance(diff, DifferenceAdded):
                    lines += Formatter.format_added(diff)
                elif isinstance(diff, DifferenceRemoved):
                    lines += Formatter.format_removed(diff)
                else:
                    lines += Formatter.format(diff)
            lines.append(Formatter.newline(''))
    return ''.join(lines)


class RevisionFormatTranslator(model.ModelView):
    'Revision Translator'

    __name__ = 'diff_blame.revision_format_translator'

    author_label = fields.Char('AUTHOR')
    target_label = fields.Char('target')


class RevisionBlame(model.CoopView):
    'Revision Blame View'

    __name__ = 'diff_blame.revision_blame'

    model_id = fields.Integer('ID', readonly=True)
    model_name = fields.Char('Model Name', readonly=True)
    record_name = fields.Char('Record Name', readonly=True)
    blame_text = fields.Text('Blame', readonly=True)
    current_page = fields.Integer('Current Page')
    total_pages = fields.Integer('Total Pages', readonly=True)

    @classmethod
    def __setup__(cls):
        super(RevisionBlame, cls).__setup__()
        cls._buttons.update({
                'next_revisions': {
                    'readonly': Equal(Eval('current_page'),
                        Eval('total_pages')),
                    'icon': 'tryton-go-next',
                    },
                'prev_revisions': {
                    'readonly': Equal(Eval('current_page', 1), 1),
                    'icon': 'tryton-go-previous'
                    }
                })

    @model.CoopView.button_change('model_id', 'model_name', 'blame_text',
        'current_page', 'total_pages')
    def next_revisions(self):
        if self.current_page == self.total_pages:
            return
        self.current_page += 1
        instance = Pool().get(self.model_name)(self.model_id)
        self.blame_text = generate_diff(instance,
            self.current_page, self.total_pages)

    @model.CoopView.button_change('model_id', 'model_name', 'blame_text',
        'current_page', 'total_pages')
    def prev_revisions(self):
        if (self.current_page - 1) >= 0:
            self.current_page -= 1
            instance = Pool().get(self.model_name)(self.model_id)
            self.blame_text = generate_diff(instance,
                self.current_page, self.total_pages)


class RevisionBlameWizard(Wizard):
    'Revision Blame Wizard'

    __name__ = 'diff_blame.revision_blame_wizard'

    start_state = 'revision_blame'

    revision_blame = StateView(
        'diff_blame.revision_blame',
        'cog_utils.revision_blame_view_form',
        [Button('Done', 'end', 'tryton-ok')]
    )

    @classmethod
    def __setup__(cls):
        super(RevisionBlameWizard, cls).__setup__()
        cls._error_messages.update({
                'active_model_no_history': 'The model %s has no revisions.'
                })

    def has_history(self, instance):
        if bool(instance._history) is False:
            self.raise_user_error('active_model_no_history')

    def get_total_pages(self, instance, model_id, per_page=10):
        cursor = Transaction().connection.cursor()
        history = instance.__table_history__()
        cursor.execute(*history.select(
                Count(history.id),
                where=(history.id == model_id)))
        rowcount = cursor.fetchone()[0]
        return int(math.ceil(rowcount / float(per_page)))

    def default_revision_blame(self, fields):
        transaction_ctx = Transaction().context
        model_id = transaction_ctx.get('active_id', None)
        model_name = transaction_ctx.get('active_model', None)

        Model = Pool().get(model_name)
        instance = Model(model_id)
        self.has_history(Model)

        current_page = 1
        total_pages = self.get_total_pages(instance, model_id)
        return {
            'model_id': model_id,
            'model_name': model_name,
            'record_name': instance.rec_name,
            'blame_text': generate_diff(instance, current_page, total_pages),
            'current_page': current_page,
            'total_pages': total_pages,
        }

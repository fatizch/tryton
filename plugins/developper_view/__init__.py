import gtk
import gettext

from tryton.common import popup_menu
from tryton.gui.window import Window
from tryton.gui.window.view_form.view.form_gtk.many2one import Many2One
from tryton.gui.window.view_form.view import list as tryton_list
from tryton.gui.window.form import Form

_ = gettext.gettext


old_populate = popup_menu.populate


def new_populate(menu, model, record, title='', field=None, context=None):
    if record is None:
        return
    elif isinstance(record, (int, long)):
        if record < 0:
            return
    elif record.id < 0:
        return

    def id_(record):
        if not isinstance(record, (int, long)):
            return record.id
        return record

    def dev_edit(menuitem):
        with Window(hide_current=True, allow_similar=True):
            Window.create(
                model, view_ids=[], res_id=id_(record),
                name='Developer view (%s %i)' % (model, id_(record)),
                mode=['form'], context={'developper_view': True})

    old_populate(menu, model, record, title, field, context)

    def set_menu(menu):
        edit, notes = None, None
        for idx, node in enumerate(menu.get_children()):
            if node.get_label() == _('Notes...'):
                notes = idx
            elif node.get_label() == ('Dev Edit...'):
                edit = idx
            elif node.get_submenu():
                set_menu(node.get_submenu())

        if edit:
            return
        dev_edit_item = gtk.MenuItem('Dev Edit...')
        dev_edit_item.connect('activate', dev_edit)
        menu.insert(dev_edit_item, notes + 1)

    set_menu(menu)

    menu.show_all()


popup_menu.populate = new_populate
tryton_list.populate = new_populate


old_popup = Many2One._populate_popup.im_func


def new_popup(self, widget, menu):
    old_popup(self, widget, menu)
    value = self.field.get(self.record)
    if self.has_target(value):
        model = self.get_model()
        target_id = self.id_from_value(value)

        def dev_edit(menuitem):
            with Window(hide_current=True, allow_similar=True):
                Window.create(
                    model, view_ids=[], res_id=target_id,
                    name='Developer view (%s %i)' % (model, target_id),
                    mode=['form'], context={
                        'developper_view': True,
                        })

        dev_edit_item = gtk.MenuItem('Dev Edit...')
        dev_edit_item.connect('activate', dev_edit)
        menu.append(dev_edit_item)
    return True


Many2One._populate_popup = new_popup


old_toolbar = Form.create_toolbar.im_func


def new_create_toolbar(self, toolbars):

    model = self.screen.model_name

    def dev_edit():
        if not self.screen.current_record:
            return

        record_id = self.screen.current_record.id
        with Window(hide_current=True, allow_similar=True):
            Window.create(
                model, view_ids=[], res_id=record_id,
                name='Developer view (%s %i)' % (model, record_id),
                mode=['form'], context={
                    'developper_view': True,
                    })

    toolbar = old_toolbar(self, toolbars)
    qbutton = gtk.ToolButton('tryton-preferences-system')
    qbutton.set_label('Dev Edit...')
    qbutton.connect('clicked', lambda b: dev_edit())
    toolbar.insert(qbutton, -1)
    return toolbar


Form.create_toolbar = new_create_toolbar


def get_plugins(model):
    return []

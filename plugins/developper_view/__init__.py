import gtk
from tryton.common import popup_menu
from tryton.gui.window import Window


old_populate = popup_menu.populate


def new_populate(menu, model, record, title='', field=None):
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
            Window.create([], model, id_(record),
                mode=['form'], context={
                    'developper_read_view': True,
                    'disable_main_toolbar': True,
                    'disable_main_menu': True,
                    })

    old_populate(menu, model, record, title, field)

    if title:
        # Look for the last created submenu, it should match the current title
        action_menu = None
        for cur_menu in menu.get_children():
            sub_menu = cur_menu.get_submenu()
            if sub_menu:
                action_menu = sub_menu
        if action_menu is None:
            return
    else:
        action_menu = menu

    if len(action_menu):
        action_menu.append(gtk.SeparatorMenuItem())
    dev_edit_item = gtk.MenuItem('Dev Edit...')
    dev_edit_item.connect('activate', dev_edit)
    action_menu.append(dev_edit_item)


popup_menu.populate = new_populate


def get_plugins(model):
    return []

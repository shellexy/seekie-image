"""让 pywebview 的 GTK 后端通过 Gtk.FileChooserNative 使用 XDG Portal 文件对话框。"""
import os
os.environ.setdefault('GTK_USE_PORTAL', '1')

import importlib.abc
import logging
import sys

logger = logging.getLogger('kde_native_dialog_patch')

_PATCH_FLAG = '_kde_portal_patched'
_TARGET = 'webview.platforms.gtk'


def _install_gtk_native_file_dialog():
    from webview import FileDialog
    from webview.platforms.gtk import BrowserView

    if getattr(BrowserView.create_file_dialog, _PATCH_FLAG, False):
        return

    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk as gtk

    def create_file_dialog(self, dialog_type, directory, allow_multiple,
                           save_filename, file_types):
        if dialog_type == FileDialog.FOLDER:
            action = gtk.FileChooserAction.SELECT_FOLDER
            title = self.localization['linux.openFolder']
            accept_label = '_Open'
        elif dialog_type == FileDialog.OPEN:
            action = gtk.FileChooserAction.OPEN
            title = (self.localization['linux.openFiles'] if allow_multiple
                     else self.localization['linux.openFile'])
            accept_label = '_Open'
        elif dialog_type == FileDialog.SAVE:
            action = gtk.FileChooserAction.SAVE
            title = self.localization['global.saveFile']
            accept_label = '_Save'
        else:
            raise ValueError(f'Unknown dialog type: {dialog_type}')

        dialog = gtk.FileChooserNative.new(
            title, self.window, action, accept_label, '_Cancel')
        dialog.set_select_multiple(allow_multiple)
        if directory:
            dialog.set_current_folder(directory)
        self._add_file_filters(dialog, file_types)
        if dialog_type == FileDialog.SAVE and save_filename:
            dialog.set_current_name(save_filename)

        response = dialog.run()

        # FileChooserNative 用的是 ACCEPT，不是 OK
        if response == gtk.ResponseType.ACCEPT:
            if dialog_type == FileDialog.SAVE:
                file_name = (dialog.get_filename(),)
            else:
                file_name = dialog.get_filenames()
        else:
            file_name = None

        dialog.destroy()
        return file_name

    setattr(create_file_dialog, _PATCH_FLAG, True)
    BrowserView.create_file_dialog = create_file_dialog
    logger.info('kde_native_dialog_patch: GTK FileChooserNative patch installed')


def _apply_if_gtk_loaded():
    if _TARGET in sys.modules:
        _install_gtk_native_file_dialog()


class _GtkHook(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != _TARGET:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, 'find_spec'):
                continue
            spec = finder.find_spec(fullname, path, target)
            if spec is not None:
                spec.loader = _HookLoader(spec.loader)
                return spec
        return None


class _HookLoader(importlib.abc.Loader):
    def __init__(self, original):
        self._original = original

    def create_module(self, spec):
        if hasattr(self._original, 'create_module'):
            return self._original.create_module(spec)
        return None

    def exec_module(self, module):
        self._original.exec_module(module)
        _install_gtk_native_file_dialog()


def _install_hook():
    for finder in sys.meta_path:
        if isinstance(finder, _GtkHook):
            return
    sys.meta_path.insert(0, _GtkHook())


_install_hook()
_apply_if_gtk_loaded()

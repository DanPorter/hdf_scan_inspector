"""
HDF Scan Inspector - Folder viewer

By Dan Porter
Diamond Light Source Ltd
2024
"""

import os
import time
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from threading import Thread

from hdf_scan_inspector.hdf_functions import EXTENSIONS, DEFAULT_ADDRESS, address_name, \
    list_files, get_hdf_value, list_path_time_files, display_timestamp
from hdf_scan_inspector.hdf_functions import search_filename_in_folder, search_hdf_files
from hdf_scan_inspector.tk_functions import create_root, topmenu, select_hdf_file, open_close_all_tree, select_folder
from hdf_scan_inspector.tk_functions import light_theme, dark_theme
from hdf_scan_inspector.hdf_tree_gui import HDFViewer, HDFMapView, dataset_selector


class _FolderGui:
    """Inheretence class"""
    root = None
    tree = None
    filepath = None

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_menu(self):
        menu = {
            'File': {
                'New window': self.menu_new_window,
                'Open Folder Viewer': self.menu_folder_browser,
                'Open Folder list': self.menu_folder_files,
                'Open Folder plot': self.menu_folder_plot,
                'Open file inspector': self.menu_file_gui,
                'Open image GUI': self.menu_image_gui,
                'Open dataset GUI': self.menu_namespace_gui
            },
            'Search': {
                'Search for file': self.menu_search_file,
                'Search hdf files for dataset': self.menu_search_dataset,
            },
            'Theme': {
                'Dark': dark_theme,
                'Light': light_theme,
            }
        }

        topmenu(self.root, menu)

    def ini_treeview(self):
        main = ttk.Frame(self.root)
        main.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        frm = ttk.Frame(main)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        tree = ttk.Treeview(frm, columns=('modified', 'files', 'dataset', 'filepath'), selectmode='browse')
        tree.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        tree.configure(yscrollcommand=var.set)

        # Populate tree
        tree.heading("#0", text="Folder")
        tree.column("#0", width=200)
        tree.heading("modified", text='Modified')
        tree.column("modified", width=200)
        tree.heading("files", text='Files')
        tree.column("files", width=100)
        tree.heading("dataset", text=address_name(DEFAULT_ADDRESS))
        tree.column("dataset", width=400)

        tree.bind("<Button-3>", self.right_click_menu(frm, tree))
        return tree

    "======================================================"
    "================= menu functions ====================="
    "======================================================"

    def menu_new_window(self):
        pass

    def menu_folder_browser(self):
        filepath, folderpath = self.get_filepath()
        HDFFolderViewer(folderpath, parent=self.root)

    def menu_folder_files(self):
        filepath, folderpath = self.get_filepath()
        HDFFolderFiles(folderpath, parent=self.root)

    def menu_folder_plot(self):
        from .hdf_plot_gui import HDFFolderPlotViewer
        filepath, folderpath = self.get_filepath()
        HDFFolderPlotViewer(folderpath, parent=self.root)

    def menu_file_gui(self):
        filepath, folderpath = self.get_filepath()
        if filepath:
            HDFViewer(filepath, parent=self.root)
        else:
            HDFViewer(folderpath, parent=self.root)

    def menu_plot_gui(self):
        from .hdf_plot_gui import HDFPlotViewer
        filepath, folderpath = self.get_filepath()
        if filepath:
            HDFPlotViewer(filepath, parent=self.root)
        else:
            HDFPlotViewer(folderpath, parent=self.root)

    def menu_image_gui(self):
        from .hdf_image_gui import HDFImageViewer
        filepath, folderpath = self.get_filepath()
        if filepath:
            HDFImageViewer(filepath, parent=self.root)
        else:
            HDFImageViewer(folderpath, parent=self.root)

    def menu_namespace_gui(self):
        filepath, folderpath = self.get_filepath()
        if filepath:
            HDFMapView(filepath, parent=self.root)
        else:
            HDFMapView(folderpath, parent=self.root)

    def menu_search_file(self):
        filepath, folderpath = self.get_filepath()
        HDFFileSearch(folderpath, parent=self.root)

    def menu_search_dataset(self):
        pass

    def menu_expand_all(self):
        open_close_all_tree(self.tree, "", True)

    def menu_collapse_all(self):
        open_close_all_tree(self.tree, "", False)

    def menu_copy_path(self):
        filepath, folderpath = self.get_filepath()
        self.root.clipboard_clear()
        if filepath:
            self.root.clipboard_append(filepath)
        else:
            self.root.clipboard_append(folderpath)

    def right_click_menu(self, frame, tree):
        # right-click menu - file options
        m_file = tk.Menu(frame, tearoff=0)
        m_file.add_command(label="Copy", command=self.menu_copy_path)
        m_file.add_command(label="open Treeview", command=self.menu_file_gui)
        m_file.add_command(label="open Plot", command=self.menu_plot_gui)
        m_file.add_command(label="open Image", command=self.menu_image_gui)
        m_file.add_command(label="open Namespace", command=self.menu_namespace_gui)
        # right-click menu - folder options
        m_folder = tk.Menu(frame, tearoff=0)
        m_folder.add_command(label="Copy", command=self.menu_copy_path)
        m_folder.add_command(label="Open Folder Datasets", command=self.menu_folder_files)
        m_folder.add_command(label="Open Folder Plots", command=self.menu_folder_plot)

        def menu_popup(event):
            # select item
            iid = tree.identify_row(event.y)
            if iid:
                tree.selection_set(iid)
                filename, foldername = self.get_filepath()
                if filename:
                    try:
                        m_file.tk_popup(event.x_root, event.y_root)
                    finally:
                        m_file.grab_release()
                else:
                    try:
                        m_folder.tk_popup(event.x_root, event.y_root)
                    finally:
                        m_file.grab_release()
        return menu_popup

    "======================================================"
    "================ general functions ==================="
    "======================================================"

    def get_filepath(self):
        """
        Return filepath and folderpath of current selection
        :returns hdf_filename: str full filepath or None if selection isn't a file
        :returns foldername: str folder path
        """
        return None, self.filepath.get()

    def _delete_tree(self):
        self.tree.delete(*self.tree.get_children())

    def _on_close(self):
        # self.root.unbind_all('<KeyPress>')
        self.root.destroy()

    "======================================================"
    "================ button functions ===================="
    "======================================================"

    def browse_folder(self):
        folder_directory = select_folder(parent=self.root)
        if folder_directory:
            self.filepath.set(folder_directory)

    def up_folder(self):
        self.filepath.set(os.path.abspath(os.path.join(self.filepath.get(), '..')))


class HDFFolderViewer(_FolderGui):
    """
    HDF Folder Viewer - display cascading hierarchical files within a directory, with data from HDF files
        HDFFolderViewer()
    Simple ttk interface for browsing folders containing HDF files.
     - Double-Click on folder to enter that folder
     - Expand (>) folder to view HDF files with selected extension
     - Double-Click file to open in new window
     - Select a Dataset address to display this from each file (this can be slow for large folders)
     - Use the search bar to search for text within the diplayed values of files
     - type directly to search select folders

    :param initial_directory: str or None*, if str opens this folder initially
    :param parent: tk root
    """

    def __init__(self, initial_directory=None, parent=None):

        self.root = create_root('HDF Folder Viewer', parent=parent)

        # Variables
        self.search_str = ""
        self.search_time = time.time()
        self.search_reset = 3.0  # seconds
        self.filepath = tk.StringVar(self.root, os.path.abspath('.'))
        self.extension = tk.StringVar(self.root, EXTENSIONS[0])
        self.address = tk.StringVar(self.root, DEFAULT_ADDRESS)
        self.show_hidden = tk.BooleanVar(self.root, False)
        self.read_datasets = tk.BooleanVar(self.root, True)
        self.search_box = tk.StringVar(self.root, '')
        self.search_matchcase = tk.BooleanVar(self.root, False)
        self.search_wholeword = tk.BooleanVar(self.root, True)
        self.select_action = tk.StringVar(self.root, '')

        "----------- MENU -----------"
        self.ini_menu()

        "----------- Dataset -----------"
        self.ini_dataset()

        "----------- Search -----------"
        self.ini_search()

        "----------- Folder -----------"
        self.ini_folderpath()

        "----------- TreeView -----------"
        self.tree = self.ini_treeview()
        self.tree['displaycolumns'] = ('modified', 'files', 'dataset')  # hide columns
        self.tree.bind("<<TreeviewOpen>>", self.tree_open)
        self.tree.bind("<Double-1>", self.on_double_click)

        "-------------------------Start Mainloop------------------------------"
        if initial_directory:
            self.filepath.set(initial_directory)
        self._list_folders()
        self.tree.bind_all('<KeyPress>', self.on_key_press)
        if parent is None:
            light_theme()
            self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_folderpath(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Browse', command=self.browse_folder, width=8)
        var.pack(side=tk.LEFT)
        var = ttk.Button(frm, text=u'\u2191', command=self.up_folder)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self._list_folders)
        var.bind('<KP_Enter>', self._list_folders)

        var = ttk.Checkbutton(frm, text='Show hidden', variable=self.show_hidden, command=self._list_folders)
        var.pack(side=tk.LEFT)

    def ini_dataset(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Dataset', command=self.select_dataset, width=8)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.address)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self._thread_update_datasets)
        var.bind('<KP_Enter>', self._thread_update_datasets)

        var = ttk.Checkbutton(frm, text='Read dataset', variable=self.read_datasets)
        var.pack(side=tk.LEFT)

        var = ttk.Label(frm, text=' | Extension: ')
        var.pack(side=tk.LEFT)
        var = ttk.OptionMenu(frm, self.extension, None, *EXTENSIONS)
        var.pack(side=tk.LEFT)

    def ini_search(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Search', command=self.fun_search, width=8)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.search_box)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_search)
        var.bind('<Return>', self.fun_search)
        var.bind('<KP_Enter>', self.fun_search)

        var = ttk.Checkbutton(frm, variable=self.search_matchcase, text='Case')
        var.pack(side=tk.LEFT)
        var = ttk.Checkbutton(frm, variable=self.search_wholeword, text='Word')
        var.pack(side=tk.LEFT)

        # select action
        _actions = ['Tree Viewer', 'Image Viewer']
        var = ttk.Label(frm, text='| Open: ')
        var.pack(side=tk.LEFT)
        var = ttk.OptionMenu(frm, self.select_action, None, *_actions)
        var.pack(side=tk.LEFT)
        self.select_action.set(_actions[0])

    "======================================================"
    "================ button functions ===================="
    "======================================================"

    def get_filepath(self):
        """
        Return filepath and folderpath of current selection
        :returns hdf_filename: str full filepath or None if selection isn't a file
        :returns foldername: str folder path
        """
        hdf_filename = None
        foldername = self.filepath.get()
        for iid in self.tree.selection():
            item = self.tree.item(iid)
            parent = self.tree.item(self.tree.parent(iid))
            if item['values'][1] == '' and item['text'] != '..':  # item is a file
                hdf_filename = os.path.join(self.filepath.get(), parent['text'], item['text'])
            else:  # item is a folder
                foldername = os.path.join(foldername, item['text'])
        return hdf_filename, foldername

    def browse_folder(self):
        super().browse_folder()
        self._list_folders()

    def up_folder(self):
        super().up_folder()
        self._list_folders()

    def select_dataset(self):
        """Select dataset button, fill out datasets"""
        hdf_filename, folder = self.get_filepath()
        if hdf_filename is None:
            # Select file to get address from
            hdf_filename = select_hdf_file(self.root)
        if hdf_filename:
            hdf_address = dataset_selector(hdf_filename, "Select a datasaet address", parent=self.root)
            if hdf_address:
                self.address.set(hdf_address)
                self._thread_update_datasets()

    "======================================================"
    "================= event functions ===================="
    "======================================================"

    def tree_open(self, event=None):
        """Add list of files below folder on folder expand"""
        if not self.tree.selection():
            return
        item = self.tree.selection()[0]  # folder treeview item
        nfiles = self.tree.item(item)['values'][1]  # number of hdf files in folder
        if not nfiles:
            return
        else:
            if len(self.tree.get_children(item)) == 1:
                # remove old entries
                self.tree.delete(*self.tree.get_children(item))
                # add hdf files
                path = os.path.join(self.filepath.get(), self.tree.item(item)['text'])
                files = list_files(path, self.extension.get())
                mytime = time.time()
                for file in files:
                    mtime = display_timestamp(os.stat(file).st_mtime)
                    self.tree.insert(item, tk.END, text=os.path.basename(file), values=(mtime, '', ''))
                if self.read_datasets.get():
                    self._thread_update_datasets()
                print(f"Expanding took {time.time()-mytime:.3g} s")

    def on_double_click(self, event=None):
        """Open a folder or open a file in a new window"""
        if not self.tree.selection():
            return
        iid = self.tree.selection()[0]
        item = self.tree.item(iid)
        parent = self.tree.item(self.tree.parent(iid))
        if item['values'][1] == '' and item['text'] != '..':
            # item is a file, open file viewer
            hdf_filename = os.path.join(self.filepath.get(), parent['text'], item['text'])
            if self.select_action.get() == 'Tree Viewer':
                HDFViewer(hdf_filename, self.root)
            else:
                from .hdf_image_gui import HDFImageViewer
                HDFImageViewer(hdf_filename, parent=self.root)
        else:
            # item is a folder, open folder
            self.filepath.set(os.path.abspath(os.path.join(self.filepath.get(), item['text'])))
            self._list_folders()

    def on_key_press(self, event):
        """any key press performs search of folders, selects first matching folder"""
        # return if clicked on entry box
        # event.widget == self.tree
        if str(event.widget).endswith('entry'):
            return
        # reset search str after reset time
        ctime = time.time()
        if ctime > self.search_time + self.search_reset:
            self.search_str = ""
        # update search time, add key to query
        self.search_time = ctime
        self.search_str += event.char

        self.tree.selection_remove(self.tree.selection())
        # search folder list
        for branch in self.tree.get_children():  # folders
            folder = self.tree.item(branch)['text']
            if folder.lower().startswith(self.search_str):
                self.tree.selection_add(branch)
                self.tree.see(branch)
                break

    def fun_search(self, event=None):
        self.tree.selection_remove(self.tree.selection())
        query = self.search_box.get()
        match_case = self.search_matchcase.get()
        whole_word = self.search_wholeword.get()
        query = query if match_case else query.lower()

        for branch in self.tree.get_children():  # folders
            # folder = self.tree.item(branch)['text']
            for leaf in self.tree.get_children(branch):  # files
                item = self.tree.item(leaf)
                if len(item['values']) < 3:
                    continue
                file = item['text']
                value = item['values'][2]
                test = f"{file} {value}"
                test = test if match_case else test.lower()
                test = test.split() if whole_word else test
                if query in test:
                    self.tree.selection_add(leaf)
                    self.tree.see(leaf)

    "======================================================"
    "================= misc functions ====================="
    "======================================================"

    def _list_folders(self, event=None):
        name_time_nfiles = list_path_time_files(self.filepath.get(), self.extension.get())
        self._delete_tree()
        self.tree.insert("", tk.END, text="..", values=('', '', ''))
        hide_hidden = not self.show_hidden.get()
        for name, mtime, nfiles in name_time_nfiles:
            name_str = os.path.basename(name)
            if hide_hidden and (name_str.startswith('.') or name_str.startswith('_')):
                continue
            time_str = display_timestamp(mtime)
            if nfiles > 0:
                entry = self.tree.insert("", tk.END, text=name_str, values=(time_str, nfiles, ''))
                self.tree.insert(entry, tk.END)  # empty
                self.tree.item(entry, open=False)
            else:
                self.tree.insert("", tk.END, text=name_str, values=(time_str, nfiles, ''))

    def _update_datasets(self, event=None):
        """Update dataset values column for hdf files under open folders"""
        address = self.address.get()
        self.tree.heading("dataset", text=address_name(address))
        directory = self.filepath.get()
        for branch in self.tree.get_children():  # folders
            folder = os.path.join(directory, self.tree.item(branch)['text'])
            for leaf in self.tree.get_children(branch):  # files
                file = self.tree.item(leaf)['text']
                if file:
                    filename = os.path.join(folder, file)
                    value = get_hdf_value(filename, address, '...')
                    self.tree.set(leaf, 'dataset', value)

    def _thread_update_datasets(self, event=None):
        """Start new thread process to get dataset values"""
        th = Thread(target=self._update_datasets)
        th.start()  # will run until complete, may error if TreeView is destroyed


class HDFFolderFiles(_FolderGui):
    """
    HDF Folder Viewer - display cascading hierarchical files within a directory, with data from HDF files
        HDFFolderViewer()
    Simple ttk interface for browsing folders containing HDF files.
     - Click Add Folder to pick add the containing files with choosen extension
     - Click Select Dataset to choose a single dataset to display (arrays will display shape)
     - Use the search bar to search for text within the diplayed values
     - Double-Click on a file to open that file

    :param initial_directories: list of str, opens these folders initially
    :param parent: tk root
    """

    def __init__(self, initial_directories=(), parent=None):

        self.root = create_root('HDF Folder Viewer', parent=parent)

        # Variables
        self.filepath = tk.StringVar(self.root, '')
        self.address = tk.StringVar(self.root, DEFAULT_ADDRESS)
        self.extension = tk.StringVar(self.root, EXTENSIONS[0])
        self.search_box = tk.StringVar(self.root, '')
        self.search_matchcase = tk.BooleanVar(self.root, False)
        self.search_wholeword = tk.BooleanVar(self.root, True)
        self.select_action = tk.StringVar(self.root, '')

        "----------- MENU -----------"
        self.ini_menu()

        "----------- BROWSE -----------"
        self.ini_folderpath()

        "----------- Dataset -----------"
        self.ini_dataset()

        "----------- SEARCH -----------"
        self.ini_search()

        "----------- TreeView -----------"
        self.tree = self.ini_treeview()
        self.tree['displaycolumns'] = ("dataset",)  # hide filepath column
        self.tree.bind("<<TreeviewSelect>>", self.tree_select)
        self.tree.bind("<Double-1>", self.on_double_click)

        "-------------------------Start Mainloop------------------------------"
        if initial_directories:
            for folder in initial_directories:
                self._add_folder(folder, EXTENSIONS[0])
            self.filepath.set(initial_directories[-1])
        if parent is None:
            light_theme()
            self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_folderpath(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Add Folder', command=self.add_folder, width=12)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self.event_add_folder)
        var.bind('<KP_Enter>', self.event_add_folder)

        "----------- Extension -----------"
        var = ttk.Label(frm, text='Extension: ')
        var.pack(side=tk.LEFT)
        var = ttk.OptionMenu(frm, self.extension, None, *EXTENSIONS)
        var.pack(side=tk.LEFT)

    def ini_dataset(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Dataset', command=self.select_dataset, width=12)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.address)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self._update_datasets)
        var.bind('<KP_Enter>', self._update_datasets)

    def ini_search(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Search', command=self.fun_search, width=12)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.search_box)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_search)
        var.bind('<Return>', self.fun_search)
        var.bind('<KP_Enter>', self.fun_search)

        var = ttk.Checkbutton(frm, variable=self.search_matchcase, text='Case')
        var.pack(side=tk.LEFT)
        var = ttk.Checkbutton(frm, variable=self.search_wholeword, text='Word')
        var.pack(side=tk.LEFT)

        # select action
        _actions = ['Tree Viewer', 'Image Viewer']
        var = ttk.Label(frm, text='| Open: ')
        var.pack(side=tk.LEFT)
        var = ttk.OptionMenu(frm, self.select_action, None, *_actions)
        var.pack(side=tk.LEFT)
        self.select_action.set(_actions[0])

    "======================================================"
    "================ button functions ===================="
    "======================================================"

    def add_folder(self):
        folder_directory = filedialog.askdirectory(
            title='Select a directory',
            mustexist=True,
            parent=self.root
        )
        if folder_directory:
            self.filepath.set(folder_directory)
            self._add_folder(folder_directory, self.extension.get())

    def select_dataset(self):
        # Select file to get address from
        hdf_file = select_hdf_file(self.root)
        if hdf_file:
            hdf_address = dataset_selector(hdf_file, "Select a datasaet address", parent=self.root)
            if hdf_address:
                self.address.set(hdf_address)
                self._update_datasets()

    "======================================================"
    "================= event functions ===================="
    "======================================================"

    def event_add_folder(self, event=None):
        folder_path = self.filepath.get()
        extension = self.extension.get()
        self._add_folder(folder_path, extension)

    def _update_files(self, event=None):
        for branch in self.tree.get_children():
            folder_path = self.tree.item(branch)['text']
            file_items = self.tree.get_children(branch)
            file_list = list_files(folder_path, self.extension.get())
            if len(file_items) == len(file_list):
                continue

    def _thread_update_datasets(self, event=None):
        """Start new thread process to get dataset values"""
        th = Thread(target=self._update_datasets)
        th.start()  # will run until complete, may error if TreeView is destroyed

    def tree_select(self, event=None):
        """on selecting a file, change the filepath entry"""
        addresses = [
            self.tree.item(item)["values"][1]
            for item in self.tree.selection()
        ]
        if addresses:
            self.filepath.set(os.path.dirname(addresses[0]))

    def on_double_click(self, event=None):
        addresses = [
            self.tree.item(item)["values"][1]
            for item in self.tree.selection()
        ]
        if addresses:
            select_action = self.select_action.get()
            if select_action == 'Image Viewer':
                from .hdf_image_gui import HDFImageViewer
                HDFImageViewer(addresses[0], parent=self.root)
            else:
                HDFViewer(addresses[0], parent=self.root)

    def fun_search(self, event=None):
        self.tree.selection_remove(self.tree.selection())
        query = self.search_box.get()
        match_case = self.search_matchcase.get()
        whole_word = self.search_wholeword.get()
        query = query if match_case else query.lower()

        for branch in self.tree.get_children():  # folders
            # folder = self.tree.item(branch)['text']
            for leaf in self.tree.get_children(branch):  # files
                file = self.tree.item(leaf)['text']
                value = self.tree.item(leaf)['values'][0]
                test = f"{file} {value}"
                test = test if match_case else test.lower()
                test = test.split() if whole_word else test
                if query in test:
                    self.tree.selection_add(leaf)
                    self.tree.see(leaf)

    "======================================================"
    "================= misc functions ====================="
    "======================================================"

    def _add_folder(self, folder_path, extension):
        # check folder_path in list
        if folder_path in [self.tree.item(branch)['text'] for branch in self.tree.get_children()]:
            self._update_files()
        # Get list of files and dataset values
        file_list = list_files(folder_path, extension)
        # Create folder path branch
        branch = self.tree.insert("", tk.END, text=os.path.basename(folder_path), values=('', folder_path))
        for file_path in file_list:
            self.tree.insert(branch, tk.END, text=os.path.basename(file_path), values=('', file_path))
        self.tree.item(branch, open=True)
        self._thread_update_datasets()

    def _update_datasets(self, event=None):
        address = self.address.get()
        self.tree.heading("dataset", text=address_name(address))
        for branch in self.tree.get_children():  # folders
            folder = self.tree.item(branch)['text']
            for leaf in self.tree.get_children(branch):  # files
                # file = self.tree.item(leaf)['text']
                # filename = os.path.join(folder, file)
                filename = self.tree.set(leaf, 'filepath')
                value = get_hdf_value(filename, address, '..')
                self.tree.set(leaf, "dataset", value)


class HDFFileSearch(_FolderGui):
    """
    HDFFolderSearch
    """

    def __init__(self, initial_directory=None, parent=None):

        self.root = create_root('HDF Folder Search', parent=parent)

        # Variables
        self.filepath = tk.StringVar(self.root, os.path.abspath('.'))
        self.extension = tk.StringVar(self.root, EXTENSIONS[0])
        self.search_box = tk.StringVar(self.root, '*')
        self.search_matchcase = tk.BooleanVar(self.root, False)
        self.search_wholeword = tk.BooleanVar(self.root, False)

        "----------- MENU -----------"
        self.ini_menu()

        "----------- Folder -----------"
        self.ini_folderpath()

        "----------- Search -----------"
        self.ini_search()

        "----------- TreeView -----------"
        self.tree = self.ini_treeview()
        self.tree['displaycolumns'] = ('modified',)  # hide columns

        "-------------------------Start Mainloop------------------------------"
        if initial_directory:
            self.filepath.set(initial_directory)
        if parent is None:
            light_theme()
            self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_folderpath(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Browse', command=self.browse_folder, width=8)
        var.pack(side=tk.LEFT)
        var = ttk.Button(frm, text=u'\u2191', command=self.up_folder)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var = ttk.Button(frm, text='Search', command=self.search, width=8)
        var.pack(side=tk.LEFT)

    def ini_search(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Label(frm, text='Filename: ')
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.search_box)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self.search)
        var.bind('<KP_Enter>', self.search)

        var = ttk.Label(frm, text=' | Extension: ')
        var.pack(side=tk.LEFT)
        var = ttk.OptionMenu(frm, self.extension, None, *EXTENSIONS)
        var.pack(side=tk.LEFT)

        var = ttk.Checkbutton(frm, variable=self.search_matchcase, text='Case')
        var.pack(side=tk.LEFT)
        var = ttk.Checkbutton(frm, variable=self.search_wholeword, text='Word')
        var.pack(side=tk.LEFT)

    "======================================================"
    "================ general functions ==================="
    "======================================================"

    def get_filepath(self):
        """
        Return filepath and folderpath of current selection
        :returns hdf_filename: str full filepath or None if selection isn't a file
        :returns fodlername: str
        """
        for iid in self.tree.selection():
            hdf_filename = self.tree.item(iid)['values'][-1]
            return hdf_filename, self.filepath.get()

    def search(self, event=None):
        """
        perform file search
        :return:
        """
        topdir = self.filepath.get()
        filename = self.search_box.get()
        extension = self.extension.get()
        search_str = filename + extension
        files = search_filename_in_folder(topdir, search_str, self.search_matchcase.get())

        self._delete_tree()
        for file in files:
            time_str = display_timestamp(os.path.getmtime(file))
            name = str(file).replace(topdir + os.sep, '')
            self.tree.insert("", tk.END, text=name, values=(time_str, '', '', file))


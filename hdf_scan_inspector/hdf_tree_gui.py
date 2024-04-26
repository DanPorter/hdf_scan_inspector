"""
HDF Scan Inspector
Simple, lightweight tkGUIs for inspecting the structure of HDF and Nexus files

--- Main code ---
Functions:
    address_name - Convert hdf address to name
    load_address - Generate string describing object in hdf file
    populate_tree - Load HDF file, populate ttk.treeview object
    open_close_all_tree - Open or close all items in ttk.treeview
    search_tree - Set selection of items in treeview based on search query
    topmenu - Add a file menu to root
    select_hdf_file - Select HDF file using filedialog
    dataset_selector - Wrapper for HDFSelector
Classes:
    HDFViewer - HDF Viewer - display cascading hierarchical data within HDF file in ttk GUI
    HDFSelector - HDF Dataset Selector - simple ttk interface to view file structure and select an address

By Dan Porter
Diamond Light Source Ltd
2024
"""

import h5py
import time
import tkinter as tk
from tkinter import ttk

from hdf_scan_inspector.hdf_functions import load_hdf, address_name, eval_hdf, map_hdf, hdfobj_string
from hdf_scan_inspector.tk_functions import create_root, topmenu, select_hdf_file, open_close_all_tree
from hdf_scan_inspector.tk_functions import light_theme, dark_theme


def populate_tree(treeview, hdf_filename, openstate=True):
    """Load HDF file, populate ttk.treeview object"""

    datasets = []

    def recur_func(hdf_group, tree_group="", top_address='/'):
        for key in hdf_group:
            obj = hdf_group.get(key)
            link = hdf_group.get(key, getlink=True)
            address = top_address + key
            name = address_name(address)
            if isinstance(obj, h5py.Group):
                try:
                    nx_class = obj.attrs['NX_class'].decode() if 'NX_class' in obj.attrs else 'Group'
                except AttributeError:
                    nx_class = obj.attrs['NX_class']
                except OSError:
                    nx_class = 'Group'  # if object doesn't have attrs
                values = (nx_class, name, "")
                new_tree_group = treeview.insert(tree_group, tk.END, text=address, values=values)
                recur_func(obj, new_tree_group, address + '/')
                treeview.item(new_tree_group, open=openstate)
            elif isinstance(obj, h5py.Dataset):
                if isinstance(link, h5py.ExternalLink):
                    link_type = 'External Link'
                elif isinstance(link, h5py.SoftLink):
                    link_type = 'Soft Link'
                else:
                    link_type = 'Dataset'
                if obj.shape:
                    val = f"{obj.dtype} {obj.shape}"
                else:
                    val = str(obj[()])
                values = (link_type, name, val)
                # datasets.append(address)
                treeview.insert(tree_group, tk.END, text=address, values=values)

    with load_hdf(hdf_filename) as hdf:
        # add top level file group
        treeview.insert("", tk.END, text='/', values=('File', address_name(hdf_filename), ''))
        recur_func(hdf, "")
    return datasets


def search_tree(treeview, branch="", query="entry", match_case=False, whole_word=False):
    """
    Set selection of items in treeview based on search query
    :param treeview: ttk.treeview
    :param branch: ttk.treeview item (str)
    :param query: str search query
    :param match_case: if False, select items even if the case doesn't match
    :param whole_word: if True, select only items where query matches final element of address
    :return:
    """
    query = query if match_case else query.lower()
    for child in treeview.get_children(branch):
        search_tree(treeview, child, query, match_case, whole_word)
        address = treeview.item(child)['text']
        address = address if match_case else address.lower()
        address = address.split('/')[-1] if whole_word else address
        if (whole_word and query == address) or (not whole_word and query in address):
            treeview.selection_add(child)
            treeview.see(child)


def right_click_menu(frame, tree):
    """
    Create right-click context menu for hdf_tree objects
    :param frame:
    :param tree:
    :return:
    """

    def copy_address():
        for iid in tree.selection():
            frame.master.clipboard_clear()
            frame.master.clipboard_append(tree.item(iid)['text'])

    def copy_name():
        for iid in tree.selection():
            frame.master.clipboard_clear()
            frame.master.clipboard_append(tree.item(iid)['values'][-2])

    def copy_value():
        for iid in tree.selection():
            frame.master.clipboard_clear()
            frame.master.clipboard_append(tree.item(iid)['values'][-1])

    # right-click menu - file options
    m = tk.Menu(frame, tearoff=0)
    m.add_command(label="Copy address", command=copy_address)
    m.add_command(label="Copy name", command=copy_name)
    m.add_command(label="Copy value", command=copy_value)

    def menu_popup(event):
        # select item
        iid = tree.identify_row(event.y)
        if iid:
            tree.selection_set(iid)
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()

    return menu_popup


class HDFViewer:
    """
    HDF Viewer - display cascading hierarchical data within HDF file in ttk GUI
        HDFViewer("filename.h5")
    Simple ttk interface for browsing HDF file structures.
     - Click Browse or File>Select File to pick a HDF, H5 or NeXus file
     - Collapse and expand the tree to view the file structure
     - Search for addresses using the search bar
     - Click on a dataset or group to view stored attributes and data

    :param hdf_filename: str or None*, if str opens this file initially
    :param parent: tk root
    """

    def __init__(self, hdf_filename=None, parent=None):

        self.root = create_root('HDF Reader', parent=parent)

        # Variables
        self.dataset_list = []  # not currently used
        self.filepath = tk.StringVar(self.root, '')
        self.expandall = tk.BooleanVar(self.root, True)
        self.expression_box = tk.StringVar(self.root, '')
        self.search_box = tk.StringVar(self.root, '')
        self.search_matchcase = tk.BooleanVar(self.root, False)
        self.search_wholeword = tk.BooleanVar(self.root, True)

        "----------- MENU -----------"
        menu = {
            'File': {
                'Select File': self.select_file,
                'Reload': self.populate_tree,
                'Open plot GUI': self.menu_plot_gui,
                'Open image GUI': self.menu_image_gui,
                'Open namespace GUI': self.menu_namepace_gui,
            },
            'HDF': {
                'Expand all': self.menu_expand_all,
                'Collapse all': self.menu_collapse_all,
            },
            'Theme': {
                'Dark': dark_theme,
                'Light': light_theme,
            }
        }

        topmenu(self.root, menu)

        "----------- BROWSE -----------"
        self.ini_browse()

        "----------- SEARCH -----------"
        self.ini_search()

        "-------- EXPRESSION ----------"
        self.ini_expression()

        "----------- TreeView -----------"
        self.tree, self.text = self.ini_treeview()

        "-------- Start Mainloop ------"
        if hdf_filename:
            self.filepath.set(hdf_filename)
            self.populate_tree()
        if parent is None:
            light_theme()
            self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_browse(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Browse', command=self.select_file, width=10)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Checkbutton(frm, variable=self.expandall, text='Expand', command=self.check_expand)
        var.pack(side=tk.LEFT)

    def ini_search(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Search', command=self.fun_search, width=10)
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

    def ini_expression(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Expression', command=self.fun_expression, width=10)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.expression_box)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_expression_reset)
        var.bind('<Return>', self.fun_expression)
        var.bind('<KP_Enter>', self.fun_expression)

    def ini_treeview(self):
        """Return tktreeview, tktext"""
        main = ttk.Frame(self.root)
        main.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        frm = ttk.Frame(main)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        tree = ttk.Treeview(frm, columns=('type', 'name', 'value'), selectmode='browse')
        tree.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        tree.configure(yscrollcommand=var.set)

        # Populate tree
        tree.heading("#0", text="HDF Address")
        tree.column("#0", minwidth=50, width=400)
        tree.column("type", width=100, anchor='c')
        tree.column("name", width=100, anchor='c')
        tree.column("value", width=200, anchor='c')
        tree.heading("type", text="Type")
        tree.heading("name", text="Name")
        tree.heading("value", text="Value")
        tree.bind("<<TreeviewSelect>>", self.tree_select)
        tree.bind("<Double-1>", self.on_double_click)
        tree.bind("<Button-3>", right_click_menu(frm, tree))

        "----------- TextBox -----------"
        frm = ttk.Frame(main)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        text = tk.Text(frm, wrap=tk.NONE, width=50)
        text.pack(fill=tk.BOTH, expand=tk.YES)

        var = tk.Scrollbar(frm, orient=tk.HORIZONTAL)
        var.pack(side=tk.BOTTOM, fill=tk.X)
        var.config(command=text.xview)

        return tree, text

    "======================================================"
    "================= menu functions ====================="
    "======================================================"

    def menu_expand_all(self):
        open_close_all_tree(self.tree, "", True)

    def menu_collapse_all(self):
        open_close_all_tree(self.tree, "", False)

    def menu_plot_gui(self):
        from .hdf_plot_gui import HDFPlotViewer
        HDFPlotViewer(self.filepath.get(), parent=self.root)

    def menu_image_gui(self):
        from .hdf_image_gui import HDFImageViewer
        HDFImageViewer(self.filepath.get(), parent=self.root)

    def menu_namepace_gui(self):
        HDFMapView(self.filepath.get(), parent=self.root)

    "======================================================"
    "================ general functions ==================="
    "======================================================"

    def check_expand(self):
        open_close_all_tree(self.tree, "", self.expandall.get())

    def _delete_tree(self):
        self.tree.delete(*self.tree.get_children())

    def populate_tree(self):
        self._delete_tree()
        self.dataset_list = populate_tree(self.tree, self.filepath.get(), self.expandall.get())

    "======================================================"
    "================= event functions ===================="
    "======================================================"

    def tree_select(self, event=None):
        self.text.delete('1.0', tk.END)
        addresses = [self.tree.item(item)["text"] for item in self.tree.selection()]
        if addresses:
            out = hdfobj_string(self.filepath.get(), addresses[0])
            self.text.insert('1.0', out)

    def on_double_click(self, event=None):
        addresses = [self.tree.item(item)["values"][1] for item in self.tree.selection()]
        if addresses and addresses[0] == 'data':
            from .hdf_image_gui import HDFImageViewer
            HDFImageViewer(self.filepath.get(), parent=self.root)

    def select_file(self, event=None):
        filename = select_hdf_file(self.root)
        if filename:
            self.filepath.set(filename)
            self.populate_tree()

    def fun_search(self, event=None):
        self.tree.selection_remove(self.tree.selection())
        search_tree(
            treeview=self.tree,
            branch="",
            query=self.search_box.get(),
            match_case=self.search_matchcase.get(),
            whole_word=self.search_wholeword.get()
        )

    def fun_expression(self, event=None):
        self.text.delete('1.0', tk.END)
        expression = self.expression_box.get()
        out_str = f">>> {expression}\n"
        try:
            with load_hdf(self.filepath.get()) as hdf:
                out = eval_hdf(hdf, expression)
        except NameError as ne:
            out = ne
        out_str += f"{out}"
        self.text.insert('1.0', out_str)


class HDFSelector:
    """
    HDF Dataset Selector - simple ttk interface to view file structure and select an address
    Usage:
        address = HDFSelector("hdf_file.h5").show()
    Upon opening, the GUI will wait for until a dataset address is selected.
    Double-click on a dataset to return the address of that dataset.

    :param hdf_filename: str filename of HDF file
    :param message: str message to display
    """

    def __init__(self, hdf_filename, message="", parent=None):

        self.root = create_root('HDF Dataset Selector', parent=parent)

        # parameters + variables
        self.output = ""
        self.search_str = ""
        self.search_time = time.time()
        self.search_reset = 3.0  # seconds
        self.filepath = tk.StringVar(self.root, hdf_filename)
        self.expandall = tk.BooleanVar(self.root, False)

        "----------- Message -----------"
        self.ini_message(message)

        "----------- FilePath -----------"
        self.ini_filepath()

        "----------- TreeView -----------"
        self.tree = self.ini_treeview()

        "--------- Start Mainloop -------"
        populate_tree(self.tree, hdf_filename, False)
        self.root.bind_all('<KeyPress>', self.on_key_press)
        if parent is None:
            light_theme()
            # self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_message(self, message):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Label(frm, text=message, font=('TkHeadingFont', 12, "bold italic"))
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH, padx=6, pady=6)

    def ini_filepath(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Entry(frm, textvariable=self.filepath, state="readonly")
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Checkbutton(frm, variable=self.expandall, text='Expand', command=self.check_expand)
        var.pack(side=tk.LEFT)

    def ini_treeview(self):
        """return tkTreeView"""
        main = ttk.Frame(self.root)
        main.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        frm = ttk.Frame(main)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        tree = ttk.Treeview(frm, columns=('type', 'name', 'value'), selectmode='browse')
        tree.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        tree.configure(yscrollcommand=var.set)

        # Populate tree
        tree.heading("#0", text="HDF Address")
        tree.column("#0", minwidth=50, width=400)
        tree.column("type", width=100, anchor='c')
        tree.column("name", width=100, anchor='c')
        tree.column("value", width=200, anchor='c')
        tree.heading("type", text="Type")
        tree.heading("name", text="Name")
        tree.heading("value", text="Value")
        tree.bind("<Double-1>", self.on_double_click)
        return tree

    "======================================================"
    "================= event functions ===================="
    "======================================================"

    def check_expand(self):
        open_close_all_tree(self.tree, "", self.expandall.get())

    def on_key_press(self, event):
        # reset search str after reset time
        ctime = time.time()
        if ctime > self.search_time + self.search_reset:
            self.search_str = ""
        # update search time, add key to query
        self.search_time = ctime
        self.search_str += event.char

        def search(branch):
            for child in self.tree.get_children(branch):
                type_name, name = self.tree.item(child)['values'][:2]
                if name.lower().startswith(self.search_str) and type_name in ['Dataset', 'External Link']:
                    self.tree.selection_add(child)
                    self.tree.see(child)
                    return
                search(child)
        self.tree.selection_remove(self.tree.selection())
        search("")

    def on_double_click(self, event=None):
        addresses = [self.tree.item(item)["text"] for item in self.tree.selection()]
        address = addresses[0]

        with load_hdf(self.filepath.get()) as hdf:
            obj = hdf.get(address)
            if isinstance(obj, h5py.Dataset):
                self.output = address
                self.root.destroy()  # trigger wait_window

    def show(self):
        """Launches window, returns selection"""
        self.root.wait_window()  # wait for window
        self.root.unbind_all('<KeyPress>')
        self.root.destroy()
        return self.output


def dataset_selector(hdf_filename, message='', parent=None):
    """
    Wrapper for HDFSelector
    Double-click a dataset to return str address from hdf file
    :param hdf_filename: str filename of HDF file
    :param message: str message to display
    :param parent: Tk root class
    :return hdf_address: str address
    """
    return HDFSelector(hdf_filename, message, parent).show()


class HDFMapView:
    """
    HDF Dataset Map Viewer
    Creates a list of the datasets in the HDF file and the namespace hdf_name associated.
    :param hdf_filename: str hdf filepath
    :param parent: tk root
    """

    def __init__(self, hdf_filename, parent):

        filename = address_name(hdf_filename)
        self.root = create_root(f'Datasets: {filename}', parent=parent)

        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        tree = ttk.Treeview(frm, columns=('name', 'value'), selectmode='browse')
        tree.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        tree.configure(yscrollcommand=var.set)

        # Populate tree
        tree.heading("#0", text="HDF Address")
        tree.heading("name", text="Name")
        tree.heading("value", text="Value")
        tree.column("#0", width=400)
        tree.column("name", width=100)
        tree.column("value", width=100)
        tree.bind("<Button-3>", right_click_menu(frm, tree))

        with load_hdf(hdf_filename) as hdf:
            hdfmap = map_hdf(hdf)
            for name, address in hdfmap.combined.items():
                dataset = hdf[address]
                if dataset.shape:
                    val = f"{dataset.dtype} {dataset.shape}"
                else:
                    val = str(dataset[()])
                values = (name, val)
                # datasets.append(address)
                tree.insert("", tk.END, text=address, values=values)

        var = ttk.Button(self.root, text='Close', command=self.root.destroy)
        var.pack(side=tk.TOP, fill=tk.X, expand=tk.YES)


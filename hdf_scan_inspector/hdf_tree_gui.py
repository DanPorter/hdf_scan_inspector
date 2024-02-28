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

import os
import h5py
import time
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import sv_ttk


# Version
__version__ = '0.1.0'
__date__ = '2024-02-28'


def address_name(address):
    """Convert hdf address to name"""
    name = os.path.basename(address)
    return os.path.basename(name) if name == 'value' else name


def load_address(hdf_filename, address):
    """Generate string describing object in hdf file"""
    with h5py.File(hdf_filename, 'r') as hdf:
        obj = hdf.get(address)
        link = hdf.get(address, getlink=True)
        myclass = hdf.get(address, getclass=True)
        out = f"{obj.name}\n"
        out += f"{repr(obj)}\n"
        out += f"{repr(link)}\n"
        out += f"{repr(myclass)}\n"
        out += '\nattrs:\n'
        out += '\n'.join([f"{key}: {obj.attrs[key]}" for key in obj.attrs])
        if isinstance(obj, h5py.Dataset):
            out += '\n\n--- Data ---\n'
            out += f"Shape: {obj.shape}\nSize: {obj.size}\n\n"
            out += str(obj[()])
    return out


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

    with h5py.File(hdf_filename, 'r') as hdf:
        recur_func(hdf, "")
    return datasets


def open_close_all_tree(treeview, branch="", openstate=True):
    """Open or close all items in ttk.treeview"""
    treeview.item(branch, open=openstate)
    for child in treeview.get_children(branch):
        open_close_all_tree(treeview, child, openstate)  # recursively open children


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


def topmenu(root, menu_dict):
    """
    Add a file menu to root
    :param root: tkinter root
    :param menu_dict: {Menu name: {Item name: function}}
    :return: None
    """
    """Setup menubar"""
    menubar = tk.Menu(root)

    for item in menu_dict:
        men = tk.Menu(menubar, tearoff=0)
        for label, function in menu_dict[item].items():
            men.add_command(label=label, command=function)
        menubar.add_cascade(label=item, menu=men)
    root.config(menu=menubar)


def select_hdf_file(parent):
    """Select HDF file using filedialog"""
    filename = filedialog.askopenfilename(
        title='Select file to open',
        filetypes=[('NXS file', '.nxs'),
                   ('HDF file', '.h5'), ('HDF file', '.hdf'), ('HDF file', '.hdf5'),
                   ('All files', '.*')],
        parent=parent
    )
    if filename and not h5py.is_hdf5(filename):
        messagebox.showwarning(
            title='Incorrect File Type',
            message=f"File: \n{filename}\n can't be read by h5py",
            parent=parent
        )
        filename = None
    return filename


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
    """

    def __init__(self, hdf_filename=None):

        # Create Tk inter instance
        self.root = tk.Tk()
        self.root.wm_title('HDF Reader')
        # self.root.minsize(width=640, height=480)
        self.root.maxsize(width=self.root.winfo_screenwidth(), height=self.root.winfo_screenheight())

        # Variables
        self.dataset_list = []

        "----------- MENU -----------"
        menu = {
            'File': {
                'Select File': self.select_file,
                'Reload': self.populate_tree,
            },
            'HDF': {
                'Expand all': self.menu_expand_all,
                'Collapse all': self.menu_collapse_all,
            },
            'Theme': {
                'Dark': sv_ttk.use_dark_theme,
                'Light': sv_ttk.use_light_theme,
            }
        }

        topmenu(self.root, menu)

        "----------- BROWSE -----------"
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Browse', command=self.select_file)
        var.pack(side=tk.LEFT)

        self.filepath = tk.StringVar(self.root, '')
        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        self.expandall = tk.BooleanVar(self.root, True)
        var = ttk.Checkbutton(frm, variable=self.expandall, text='Expand', command=self.check_expand)
        var.pack(side=tk.LEFT)

        "----------- SEARCH -----------"
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        self.search_box = tk.StringVar(self.root, '')
        var = ttk.Entry(frm, textvariable=self.search_box)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_search)
        var.bind('<Return>', self.fun_search)
        var.bind('<KP_Enter>', self.fun_search)

        self.search_matchcase = tk.BooleanVar(self.root, False)
        self.search_wholeword = tk.BooleanVar(self.root, True)
        var = ttk.Checkbutton(frm, variable=self.search_matchcase, text='Case')
        var.pack(side=tk.LEFT)
        var = ttk.Checkbutton(frm, variable=self.search_wholeword, text='Word')
        var.pack(side=tk.LEFT)

        "----------- TreeView -----------"
        main = ttk.Frame(self.root)
        main.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        frm = ttk.Frame(main)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        self.tree = ttk.Treeview(frm, columns=('type', 'name', 'value'), selectmode='browse')
        self.tree.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=var.set)

        # Populate tree
        self.tree.heading("#0", text="HDF Address")
        self.tree.column("#0", minwidth=50, width=400)
        self.tree.column("type", width=100, anchor='c')
        self.tree.column("name", width=100, anchor='c')
        self.tree.column("value", width=200, anchor='c')
        self.tree.heading("type", text="Type")
        self.tree.heading("name", text="Name")
        self.tree.heading("value", text="Value")
        self.tree.bind("<<TreeviewSelect>>", self.tree_select)

        "----------- TextBox -----------"
        frm = ttk.Frame(main)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        self.text = tk.Text(frm, wrap=tk.NONE, width=40)
        self.text.pack(fill=tk.BOTH, expand=tk.YES)

        var = tk.Scrollbar(frm, orient=tk.HORIZONTAL)
        var.pack(side=tk.BOTTOM, fill=tk.X)
        var.config(command=self.text.xview)

        "-------------------------Start Mainloop------------------------------"
        if hdf_filename:
            self.filepath.set(hdf_filename)
            self.populate_tree()
        sv_ttk.use_light_theme()
        self.root.mainloop()

    def menu_expand_all(self):
        open_close_all_tree(self.tree, "", True)

    def menu_collapse_all(self):
        open_close_all_tree(self.tree, "", False)

    def check_expand(self):
        open_close_all_tree(self.tree, "", self.expandall.get())

    def _delete_tree(self):
        self.tree.delete(*self.tree.get_children())

    def populate_tree(self):
        self._delete_tree()
        self.dataset_list = populate_tree(self.tree, self.filepath.get(), self.expandall.get())

    def tree_select(self, event=None):
        self.text.delete('1.0', tk.END)
        addresses = [self.tree.item(item)["text"] for item in self.tree.selection()]
        if addresses:
            out = load_address(self.filepath.get(), addresses[0])
            self.text.insert('1.0', out)

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

    def __init__(self, hdf_filename, message=""):

        # Create Tk inter instance
        self.root = tk.Tk()
        self.root.wm_title('HDF Dataset Selector')
        # self.root.minsize(width=640, height=480)
        self.root.maxsize(width=self.root.winfo_screenwidth(), height=self.root.winfo_screenheight())
        self.output = ""
        self.search_str = ""
        self.search_time = time.time()
        self.search_reset = 3.0  # seconds

        "----------- Message -----------"
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Label(frm, text=message, font=('TkHeadingFont', 12, "bold italic"))
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH, padx=6, pady=6)

        "----------- FilePath -----------"
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        self.filepath = tk.StringVar(self.root, hdf_filename)
        var = ttk.Entry(frm, textvariable=self.filepath, state="readonly")
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        self.expandall = tk.BooleanVar(self.root, False)
        var = ttk.Checkbutton(frm, variable=self.expandall, text='Expand', command=self.check_expand)
        var.pack(side=tk.LEFT)

        "----------- TreeView -----------"
        main = ttk.Frame(self.root)
        main.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        frm = ttk.Frame(main)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        self.tree = ttk.Treeview(frm, columns=('type', 'name', 'value'), selectmode='browse')
        self.tree.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=var.set)

        # Populate tree
        self.tree.heading("#0", text="HDF Address")
        self.tree.column("#0", minwidth=50, width=400)
        self.tree.column("type", width=100, anchor='c')
        self.tree.column("name", width=100, anchor='c')
        self.tree.column("value", width=200, anchor='c')
        self.tree.heading("type", text="Type")
        self.tree.heading("name", text="Name")
        self.tree.heading("value", text="Value")
        self.tree.bind("<Double-1>", self.on_double_click)

        populate_tree(self.tree, hdf_filename, False)
        self.root.bind_all('<KeyPress>', self.on_key_press)

        "-------------------------Start Mainloop------------------------------"
        sv_ttk.use_light_theme()
        # self.root.mainloop()

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

        with h5py.File(self.filepath.get(), 'r') as hdf:
            obj = hdf.get(address)
            if isinstance(obj, h5py.Dataset):
                self.output = address
                self.root.destroy()

    def show(self):
        self.root.wait_window()  # wait for window
        return self.output


def dataset_selector(hdf_filename, message=''):
    """
    Wrapper for HDFSelector
    Double-click a dataset to return str address from hdf file
    :param hdf_filename: str filename of HDF file
    :param message: str message to display
    :return hdf_address: str address
    """
    return HDFSelector(hdf_filename, message).show()

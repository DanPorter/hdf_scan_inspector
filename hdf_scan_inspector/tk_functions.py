"""
tkinter funcitons
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

TEXTWIDTH = 50  # characters, width of textboxes

try:
    import sv_ttk
    light_theme = sv_ttk.use_light_theme
    dark_theme = sv_ttk.use_dark_theme
except ModuleNotFoundError:
    light_theme = lambda: print('sv_ttk not available')
    dark_theme = lambda: print('sv_ttk not available')


def create_root(window_title, parent=None):
    """Create tkinter root obect"""
    if parent:
        root = tk.Toplevel(parent)
        root.geometry(f"+{parent.winfo_x()+100}+{parent.winfo_y()+100}")
    else:
        root = tk.Tk()
    root.wm_title(window_title)
    # self.root.minsize(width=640, height=480)
    # root.maxsize(width=root.winfo_screenwidth() * 3 // 4, height=root.winfo_screenheight() * 3 // 4)
    root.maxsize(width=int(root.winfo_screenwidth() * 0.9), height=int(root.winfo_screenheight() * 0.8))
    return root


def topmenu(root, menu_dict):
    """
    Add a file menu to root
    :param root: tkinter root
    :param menu_dict: {Menu name: {Item name: function}}
    :return: None
    """
    menubar = tk.Menu(root)

    for item in menu_dict:
        men = tk.Menu(menubar, tearoff=0)
        for label, function in menu_dict[item].items():
            men.add_command(label=label, command=function)
        menubar.add_cascade(label=item, menu=men)
    root.config(menu=menubar)


def select_hdf_file(parent):
    """Select HDF file using filedialog"""
    from .hdf_functions import ishdf
    filename = filedialog.askopenfilename(
        title='Select file to open',
        filetypes=[('NXS file', '.nxs'),
                   ('HDF file', '.h5'), ('HDF file', '.hdf'), ('HDF file', '.hdf5'),
                   ('All files', '.*')],
        parent=parent
    )
    if filename and not ishdf(filename):
        messagebox.showwarning(
            title='Incorrect File Type',
            message=f"File: \n{filename}\n can't be read by h5py",
            parent=parent
        )
        filename = None
    return filename


def select_folder(parent):
    """Select folder"""
    foldername = filedialog.askdirectory(
        title='Select folder...',
        mustexist=True,
        parent=parent,
    )
    return foldername


def open_close_all_tree(treeview, branch="", openstate=True):
    """Open or close all items in ttk.treeview"""
    treeview.item(branch, open=openstate)
    for child in treeview.get_children(branch):
        open_close_all_tree(treeview, child, openstate)  # recursively open children


def treeview_sort_column(treeview: ttk.Treeview, col, reverse, sort_col=None):
    """
    Function to sort columns in ttk.Treeview,
        tree.heading("#0", command=lambda _col="#0": treeview_sort_column(tree, _col, False))
    :param treeview: ttk.Treeview instance
    :param col: str, column specifier for items to sort
    :param reverse: Bool, sort direction
    :param sort_col: str or None, sort alternative column
    :return:
    """
    if sort_col is None:
        sort_col = col
    if col == "#0":
        def item(iid):
            return treeview.item(iid)['text']
    else:
        def item(iid):
            return treeview.set(iid, col)

    items = [(item(iid), iid) for iid in treeview.get_children('')]
    items.sort(reverse=reverse)

    # rearrange items in sorted positions
    for index, (val, k) in enumerate(items):
        treeview.move(k, '', index)
        if treeview.item(k)['text'] == '..':  # keep at top of column
            treeview.move(k, '', 0)

    # reverse sort next time
    treeview.heading(sort_col, command=lambda _col=col: treeview_sort_column(treeview, _col, not reverse, sort_col))


def show_error(message, parent=None):
    """Display and raise error"""
    messagebox.showwarning(
        title="HDF File Error",
        message=message,
        parent=parent,
    )
    raise Exception(message)


"==========================================================================="
"================================= Edit Text ==============================="
"==========================================================================="


class EditText:
    """
    Simple text edit box
        next_text = EditText(old_text, tkframe).show()
    :param expression: str expression to edit
    :param parent: tk root
    """

    def __init__(self, expression, parent):
        self.output = expression
        self.root = create_root('Configure text', parent=parent)

        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        self.text = tk.Text(frm, wrap=tk.NONE, width=TEXTWIDTH)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        self.text.insert('1.0', expression)

        var = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.text.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        self.text.configure(yscrollcommand=var.set)

        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(self.root, text='Update', command=self.fun_update)
        var.pack(side=tk.TOP, fill=tk.X)

    def fun_update(self, event=None):
        """Launches window, returns selection"""
        self.output = self.text.get('1.0', tk.END)
        self.root.destroy()  # trigger wait_window

    def show(self):
        """Launches window, returns selection"""
        self.root.wait_window()  # wait for window
        self.root.destroy()
        return self.output


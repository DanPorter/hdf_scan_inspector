"""
HDF Scan Inspector
Simple, lightweight tkGUIs for inspecting the structure of HDF and Nexus files


By Dan Porter
Diamond Light Source Ltd
2024
"""

import os
import time
import threading
import tkinter as tk
from tkinter import ttk

from hdf_scan_inspector.hdf_functions import EXTENSIONS, load_hdf, ishdf, address_name, eval_hdf, list_files, \
    format_hdf, map_hdf
from hdf_scan_inspector.tk_functions import EditText, TEXTWIDTH, create_root, topmenu, select_folder, show_error
from hdf_scan_inspector.tk_functions import select_hdf_file, light_theme, dark_theme
from hdf_scan_inspector.tk_matplotlib_functions import ini_plot
from hdf_scan_inspector.hdf_tree_gui import HDFViewer, dataset_selector, HDFMapView

# parameters
DEFAULT_CONFIG = "{filename}\n{filepath}\ncmd = {scan_command}" + \
                 "\naxes = {_axes}\nsignal = {_signal}\nshape = {axes.shape}"
MAX_FILELIST_LOAD = 10


class HDFFolderPlotViewer:
    """
    HDF Folder Plot Viewer
    Contiuously watches a folder and lists the HDF files, selecting a file will plot the default axes
    :param folder: str or None*, if str opens this folder initially
    :param file_list: list of str, or None*, if list, opens files in this list
    :param text_expression: str evaluated for each file showing metadata, using {hdf_name:format}
    :param parent: tk root
    """

    def __init__(self, folder=None, file_list=None, text_expression=DEFAULT_CONFIG, parent=None):

        self.root = create_root('Folder Plot Viewer', parent=parent)
        self.root.protocol("WM_DELETE_WINDOW", self.fun_close)

        # Variables
        self.filepath = tk.StringVar(self.root, '')
        self.extension = tk.StringVar(self.root, EXTENSIONS[0])
        self.xaxis = tk.StringVar(self.root, '')
        self.yaxis = tk.StringVar(self.root, '')
        self.terminal_entry = tk.StringVar(self.root, '')
        self.active_threads = []
        self._folder_modified = None
        self._text_expression = text_expression
        self._exiting_program = False  # used when closing threads
        self._update_time = 5  # seconds
        self._debug = False

        "----------- MENU -----------"
        menu = {
            'File': {
                'Select File': self.select_folder,
                'Reload': self.add_folder,
                'Open File GUI': self.menu_file_gui,
                'Open Plot GUI': self.menu_plot_gui,
                'Open image GUI': self.menu_image_gui,
            },
            'Config': {
                'Set text expression': self.edit_expression,
                'View file datasets': self.view_namespace,
            },
            'Theme': {
                'Dark': dark_theme,
                'Light': light_theme,
            }
        }
        topmenu(self.root, menu)

        "--------- FOLDERPATH ---------"
        if file_list is None or folder is not None:
            self.ini_folderpath()

        "------------ AXES ------------"
        self.ini_axes()

        "----------- LISTBOX ----------"
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        self.file_list = self.ini_file_list(frm)

        "----------- TEXTBOX ----------"
        self.textbox, self.terminal = self.ini_textbox(frm)

        "------------ PLOT ------------"
        self.fig, self.ax1, self.plot_list, self.toolbar = ini_plot(frm)

        "-------- Start Mainloop ------"
        if folder:
            self.filepath.set(folder)
        if file_list is None:
            file_list = self.get_recent_files()[::-1]

        self.populate_file_list(file_list)
        self.item_select(0)
        thread = threading.Thread(target=self.poll_files)  # repetative check
        thread.start()
        self.active_threads.append(thread)

        if parent is None:
            light_theme()
            self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_folderpath(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Browse', command=self.select_folder, width=10)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', lambda _e: self.add_folder())
        var.bind('<KP_Enter>', lambda _e: self.add_folder())

        "----------- Extension -----------"
        var = ttk.Label(frm, text='Extension: ')
        var.pack(side=tk.LEFT)
        var = ttk.OptionMenu(frm, self.extension, None, *EXTENSIONS)
        var.pack(side=tk.LEFT)

    def ini_axes(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        var = ttk.Button(frm, text='x axis', command=self.fun_xaxis, width=8)
        var.pack(side=tk.LEFT)
        var = ttk.Button(frm, text='D', command=self.fun_default_xaxis)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.xaxis)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_expression_reset)
        var.bind('<Return>', lambda _e: self.plot_data())
        var.bind('<KP_Enter>', lambda _e: self.plot_data())

        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        var = ttk.Button(frm, text='y axis', command=self.fun_yaxis, width=8)
        var.pack(side=tk.LEFT)
        var = ttk.Button(frm, text='D', command=self.fun_default_yaxis)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.yaxis)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_expression_reset)
        var.bind('<Return>', lambda _e: self.plot_data())
        var.bind('<KP_Enter>', lambda _e: self.plot_data())

    def ini_file_list(self, frame):
        frm = ttk.Frame(frame)
        frm.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        tree = ttk.Treeview(frm, columns=('dataset', 'filepath'), selectmode='extended')
        tree.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        var.pack(side=tk.LEFT, fill=tk.Y)
        tree.configure(yscrollcommand=var.set)

        # Column headers
        tree.heading("#0", text="File")
        tree.column("#0", minwidth=50, width=200)
        tree.heading("dataset", text='')
        tree.column("dataset", width=400)
        tree['displaycolumns'] = ()  # hide columns
        tree.bind("<<TreeviewSelect>>", lambda event: self.file_select())
        tree.bind("<Double-1>", self.tree_double_click)

        # right-click menu
        m = tk.Menu(frame, tearoff=0)
        m.add_command(label="open Treeview", command=self.menu_file_gui)
        m.add_command(label="open Plot", command=self.menu_plot_gui)
        m.add_command(label="open Image", command=self.menu_image_gui)
        m.add_command(label="open Namespace", command=self.view_namespace)

        def menu_popup(event):
            # select item
            iid = tree.identify_row(event.y)
            if iid:
                tree.selection_set(iid)
                try:
                    m.tk_popup(event.x_root, event.y_root)
                finally:
                    m.grab_release()
        tree.bind("<Button-3>", menu_popup)
        return tree

    def ini_textbox(self, frame):
        frm = ttk.Frame(frame)
        frm.pack(side=tk.LEFT)

        xfrm = ttk.Frame(frm)
        xfrm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        text = tk.Text(xfrm, state=tk.DISABLED, wrap=tk.NONE, width=TEXTWIDTH)
        text.pack(fill=tk.BOTH, expand=tk.YES)
        # text.bind("<Double-1>", self.text_double_click)

        var = ttk.Scrollbar(xfrm, orient=tk.HORIZONTAL)
        var.pack(side=tk.BOTTOM, fill=tk.X)
        var.config(command=text.xview)
        text.configure(xscrollcommand=var.set)

        # Terminal
        tfrm = tk.Frame(frm, relief=tk.RIDGE)
        tfrm.pack(side=tk.TOP, fill=tk.BOTH)

        terminal = tk.Text(tfrm, state=tk.DISABLED, wrap=tk.NONE, height=3, width=TEXTWIDTH)
        terminal.pack(side=tk.LEFT, fill=tk.X, expand=tk.NO)

        var = ttk.Scrollbar(tfrm, orient=tk.VERTICAL)
        var.pack(side=tk.LEFT, fill=tk.Y)
        var.config(command=terminal.yview)
        terminal.configure(yscrollcommand=var.set)

        efrm = tk.Frame(frm, relief=tk.GROOVE)
        efrm.pack(side=tk.TOP, fill=tk.BOTH)

        var = ttk.Label(efrm, text='>>')
        var.pack(side=tk.LEFT)
        var = ttk.Entry(efrm, textvariable=self.terminal_entry)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self.fun_terminal)
        var.bind('<KP_Enter>', self.fun_terminal)

        var = ttk.Button(efrm, text='CLS', command=self.fun_terminal_cls)
        var.pack(side=tk.LEFT)

        # right-click menu
        m = tk.Menu(frame, tearoff=0)
        m.add_command(label="edit Text", command=self.edit_expression)
        m.add_command(label="open Namespace", command=self.view_namespace)

        def menu_popup(event):
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()
        text.bind("<Button-3>", menu_popup)
        return text, terminal

    "======================================================"
    "================= menu functions ====================="
    "======================================================"

    def menu_folder_gui(self):
        from .hdf_folder_gui import HDFFolderViewer
        HDFFolderViewer(self.filepath.get(), parent=self.root)

    def menu_file_gui(self):
        addresses = [
            self.file_list.item(item)["values"][1] for item in self.file_list.selection()
        ]
        if addresses:
            HDFViewer(addresses[0], parent=self.root)
        else:
            HDFViewer(self.filepath.get(), parent=self.root)

    def menu_plot_gui(self):
        addresses = [
            self.file_list.item(item)["values"][1] for item in self.file_list.selection()
        ]
        if addresses:
            HDFPlotViewer(addresses[0], parent=self.root)
        else:
            HDFPlotViewer(self.filepath.get(), parent=self.root)

    def menu_image_gui(self):
        from .hdf_image_gui import HDFImageViewer
        addresses = [
            self.file_list.item(item)["values"][1] for item in self.file_list.selection()
        ]
        if addresses:
            HDFImageViewer(addresses[0], parent=self.root)
        else:
            HDFImageViewer(self.filepath.get(), parent=self.root)

    "======================================================"
    "================ general functions ==================="
    "======================================================"

    def debug_msg(self, message):
        if self._debug:
            print(time.ctime() + f'>> {message}')

    def get_recent_files(self):
        """returns list of files created since last modified time stamp"""
        folder_path = self.filepath.get()
        try:
            mod_time = os.stat(folder_path).st_mtime
        except FileNotFoundError:
            return []

        if self._folder_modified is None:
            self._folder_modified = mod_time
            return list_files(self.filepath.get(), self.extension.get())
        elif mod_time > self._folder_modified:
            # return only files more recent than last modified
            files = sorted((
                file.path for file in os.scandir(folder_path)
                if file.name.endswith(self.extension.get())
                and file.stat().st_mtime > self._folder_modified),
                key=lambda x: os.path.getctime(x)
            )
            self._folder_modified = mod_time
            return files
        return []

    def _add_files(self, filepath_list: list[str], index: tk.END):
        for filepath in filepath_list:
            self.file_list.insert("", index, text=os.path.basename(filepath), values=('', filepath))

    def populate_file_list(self, filepath_list: list[str]):
        """list files in file list tree, from top down."""
        self._add_files(filepath_list[:MAX_FILELIST_LOAD], tk.END)
        print(filepath_list[:MAX_FILELIST_LOAD])
        if len(filepath_list) > MAX_FILELIST_LOAD:
            print(filepath_list[MAX_FILELIST_LOAD:])
            thread = threading.Thread(target=self._add_files, args=(filepath_list[MAX_FILELIST_LOAD:], tk.END))
            thread.start()
            self.active_threads.append(thread)

    def update_files(self):
        """update recent files to file_list"""
        recent_files = self.get_recent_files()
        self.debug_msg(f'folder_modified: {self._folder_modified}, recent_files: {recent_files}')
        self._add_files(recent_files, 0)

    def poll_files(self):
        while True:
            if self._exiting_program: break
            self.update_files()
            time.sleep(self._update_time)

    def add_folder(self):
        self.file_list.delete(*self.file_list.get_children())
        self._folder_modified = None
        file_list = self.get_recent_files()[::-1]
        self.populate_file_list(file_list)
        self.item_select(0)

    def plot_data(self):
        self.reset_plot()
        for item in self.file_list.selection():
            file_path = self.file_list.set(item, 'filepath')
            with load_hdf(file_path) as hdf:
                m = map_hdf(hdf)
                xvals, yvals = self.gen_xy(hdf, m)
                lab = self.file_list.item(item)['text']
                self.ax1.plot(xvals, yvals, label=lab)
        if len(self.file_list.selection()) == 1:
            ttl = self.file_list.item(self.file_list.selection()[0])["text"]
            self.ax1.set_title(ttl)
        elif len(self.file_list.selection()) > 1:
            self.ax1.legend()
        self.update_plot()

    def file_select(self):
        for item in self.file_list.selection():
            file_path = self.file_list.set(item, 'filepath')
            with load_hdf(file_path) as hdf:
                m = map_hdf(hdf)
                self.gen_text(hdf, m)
                if 'axes' in m.arrays:  # and not self.xaxis.get():
                    self.xaxis.set(m.arrays['axes'])
                if 'signal' in m.arrays:  # and not self.yaxis.get():
                    self.yaxis.set(m.arrays['signal'])
        self.plot_data()

    def item_select(self, index=0):
        children = self.file_list.get_children()
        if children:
            child_id = children[index]
            self.file_list.focus(child_id)
            self.file_list.selection_set(child_id)  # runs <<TreeViewSelect>> == self.file_select

    def gen_text(self, hdf_file, hdf_map=None):
        try:
            txt = format_hdf(hdf_file, self._text_expression, hdf_map, debug=False)
            self.textbox.configure(state=tk.NORMAL)
            self.textbox.delete('1.0', tk.END)
            self.textbox.insert('1.0', txt)
            self.textbox.configure(state=tk.DISABLED)
        except Exception as e:
            show_error(f"Error: {e}", parent=self.root)

    def edit_expression(self):
        """Double-click on text display => open config str"""
        try:
            self._text_expression = EditText(self._text_expression, self.root).show()
            self.file_select()
        except KeyError as ke:
            show_error(
                message=f"Item not recognised: {ke}",
                parent=self.root
            )

    def gen_xy(self, hdf_file, hdf_map=None):
        try:
            xvalues = eval_hdf(hdf_file, self.xaxis.get(), hdf_map)
            lenx = len(xvalues)
        except SyntaxError or NameError or TypeError:
            xvalues, lenx = [], 0
        try:
            yvalues = eval_hdf(hdf_file, self.yaxis.get(), hdf_map)
            leny = len(yvalues)
        except SyntaxError or NameError or TypeError:
            yvalues, leny = [], 0
        if lenx < leny:
            xvalues = range(leny)
        elif leny < lenx:
            yvalues = range(lenx)
        return xvalues, yvalues

    def reset_plot(self):
        self.ax1.set_xlabel(self.xaxis.get())
        self.ax1.set_ylabel(self.yaxis.get())
        self.ax1.set_title('')
        self.ax1.set_prop_cycle(None)  # reset colours
        self.ax1.legend([]).set_visible(False)
        for obj in self.ax1.lines:
            obj.remove()

    def update_plot(self):
        self.ax1.relim()
        self.ax1.autoscale(True)
        self.ax1.autoscale_view()
        self.fig.canvas.draw()
        self.toolbar.update()

    "======================================================"
    "================= event functions ===================="
    "======================================================"

    def fun_xaxis(self):
        addresses = [self.file_list.item(item)["values"][1] for item in self.file_list.selection()]
        if addresses:
            from hdf_scan_inspector.hdf_tree_gui import dataset_selector
            address = dataset_selector(addresses[0], message='Select xaxis dataset', parent=self.root)
            if address:
                self.xaxis.set(address)
                self.update_plot()

    def fun_yaxis(self):
        addresses = [self.file_list.item(item)["values"][1] for item in self.file_list.selection()]
        if addresses:
            from hdf_scan_inspector.hdf_tree_gui import dataset_selector
            address = dataset_selector(addresses[0], message='Select yaxis dataset', parent=self.root)
            if address:
                self.yaxis.set(address)
                self.update_plot()

    def fun_default_xaxis(self):
        self.xaxis.set('')

    def fun_default_yaxis(self):
        self.yaxis.set('')

    def select_folder(self, event=None):
        foldername = select_folder(self.root)
        if foldername:
            self.filepath.set(foldername)
            self.add_folder()

    def fun_terminal(self, event=None):
        expression = self.terminal_entry.get()
        out_str = f"\n>>> {expression}\n"

        addresses = [self.file_list.item(item)["values"][1] for item in self.file_list.selection()]
        if addresses:
            try:
                with load_hdf(addresses[0]) as hdf:
                    out = eval_hdf(hdf, expression)
            except NameError as ne:
                out = ne
            out_str += f"{out}"
        else:
            out_str = "\n--- No file selected ---"
        self.terminal.configure(state=tk.NORMAL)
        self.terminal.insert(tk.END, out_str)
        self.terminal.see(tk.END)
        self.terminal.configure(state=tk.DISABLED)

    def fun_terminal_cls(self, event=None):
        self.terminal.delete('1.0', tk.END)

    def tree_double_click(self, event=None):
        """Double-click on file item => open HDF Tree Viewer"""
        from hdf_scan_inspector.hdf_tree_gui import HDFViewer
        for item in self.file_list.selection():
            file_path = self.file_list.item(item)["values"][1]
            HDFViewer(file_path, parent=self.root)

    def text_double_click(self, event=None):
        """Double-click on text display => open config str"""
        try:
            self._text_expression = EditText(self._text_expression, self.root).show()
            self.file_select()
        except KeyError as ke:
            show_error(
                message=f"Item not recognised: {ke}",
                parent=self.root
            )

    def view_namespace(self, event=None):
        """Open HDFMapView gui"""
        for item in self.file_list.selection():
            file_path = self.file_list.item(item)["values"][1]
            HDFMapView(file_path, parent=self.root)

    def fun_close(self):
        """close window"""
        self.root.destroy()
        self._exiting_program = True
        for th in self.active_threads:
            print(f"Waiting for thread {th.name} to terminate...")
            th.join()
        print('Goodbye!')


class HDFPlotViewer:
    """
    HDF Plot Viewer
    Open a HDF file and plot the default axes
    :param hdf_filename: str filename
    :param text_expression: str evaluated for each file showing metadata, using {hdf_name:format}
    :param parent: tk root
    """

    def __init__(self, hdf_filename="", text_expression=DEFAULT_CONFIG, parent=None):

        self.root = create_root('HDF Plot Viewer', parent=parent)

        # Variables
        self.filepath = tk.StringVar(self.root, '')
        self.xaxis = tk.StringVar(self.root, '')
        self.yaxis = tk.StringVar(self.root, '')
        self.terminal_entry = tk.StringVar(self.root, '')
        self._text_expression = text_expression
        self._debug = False

        "----------- MENU -----------"
        menu = {
            'File': {
                'Select File': self.select_file,
                'Open File GUI': self.menu_file_gui,
                'Open image GUI': self.menu_image_gui,
            },
            'Config': {
                'Set text expression': self.edit_expression,
                'View file datasets': self.view_namespace,
            },
            'Theme': {
                'Dark': dark_theme,
                'Light': light_theme,
            }
        }
        topmenu(self.root, menu)

        "--------- filePATH ---------"
        self.ini_filepath()

        "------------ AXES ------------"
        self.ini_axes()

        "----------- TEXTBOX ----------"
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        self.textbox, self.terminal = self.ini_textbox(frm)

        "------------ PLOT ------------"
        self.fig, self.ax1, self.plot_list, self.toolbar = ini_plot(frm)

        "-------- Start Mainloop ------"
        self.filepath.set(hdf_filename)
        self.update()

        if parent is None:
            light_theme()
            self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_filepath(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Browse', command=self.select_file, width=10)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self.update)
        var.bind('<KP_Enter>', self.update)

    def ini_axes(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        var = ttk.Button(frm, text='x axis', command=self.fun_xaxis, width=8)
        var.pack(side=tk.LEFT)
        var = ttk.Button(frm, text='D', command=self.fun_default_xaxis)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.xaxis)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_expression_reset)
        var.bind('<Return>', self.update)
        var.bind('<KP_Enter>', self.update)

        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        var = ttk.Button(frm, text='y axis', command=self.fun_yaxis, width=8)
        var.pack(side=tk.LEFT)
        var = ttk.Button(frm, text='D', command=self.fun_default_yaxis)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.yaxis)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        # var.bind('<KeyRelease>', self.fun_expression_reset)
        var.bind('<Return>', self.update)
        var.bind('<KP_Enter>', self.update)

    def ini_textbox(self, frame):
        frm = ttk.Frame(frame)
        frm.pack(side=tk.LEFT)

        xfrm = ttk.Frame(frm)
        xfrm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        text = tk.Text(xfrm, state=tk.DISABLED, wrap=tk.NONE, width=TEXTWIDTH)
        text.pack(fill=tk.BOTH, expand=tk.YES)
        # text.bind("<Double-1>", self.text_double_click)

        var = ttk.Scrollbar(xfrm, orient=tk.HORIZONTAL)
        var.pack(side=tk.BOTTOM, fill=tk.X)
        var.config(command=text.xview)
        text.configure(xscrollcommand=var.set)

        # Terminal
        tfrm = tk.Frame(frm, relief=tk.RIDGE)
        tfrm.pack(side=tk.TOP, fill=tk.BOTH)

        terminal = tk.Text(tfrm, state=tk.DISABLED, wrap=tk.NONE, height=3, width=TEXTWIDTH)
        terminal.pack(side=tk.LEFT, fill=tk.X, expand=tk.NO)

        var = ttk.Scrollbar(tfrm, orient=tk.VERTICAL)
        var.pack(side=tk.LEFT, fill=tk.Y)
        var.config(command=terminal.yview)
        terminal.configure(yscrollcommand=var.set)

        efrm = tk.Frame(frm, relief=tk.GROOVE)
        efrm.pack(side=tk.TOP, fill=tk.BOTH)

        var = ttk.Label(efrm, text='>>')
        var.pack(side=tk.LEFT)
        var = ttk.Entry(efrm, textvariable=self.terminal_entry)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self.fun_terminal)
        var.bind('<KP_Enter>', self.fun_terminal)

        var = ttk.Button(efrm, text='CLS', command=self.fun_terminal_cls)
        var.pack(side=tk.LEFT)

        # right-click menu
        m = tk.Menu(frame, tearoff=0)
        m.add_command(label="edit Text", command=self.edit_expression)
        m.add_command(label="open Namespace", command=self.view_namespace)

        def menu_popup(event):
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()
        text.bind("<Button-3>", menu_popup)
        return text, terminal

    "======================================================"
    "================= menu functions ====================="
    "======================================================"

    def menu_file_gui(self):
        HDFViewer(self.filepath.get(), parent=self.root)

    def menu_image_gui(self):
        from .hdf_image_gui import HDFImageViewer
        HDFImageViewer(self.filepath.get(), parent=self.root)

    "======================================================"
    "================ general functions ==================="
    "======================================================"

    def debug_msg(self, message):
        if self._debug:
            print(time.ctime() + f'>> {message}')

    def load_file(self, filepath):
        self.reset_plot()

        if not ishdf(filepath):
            show_error(
                message=f"File: {filepath} is not a HDF file.",
                parent=self.root
            )

        with load_hdf(filepath)as hdf:
            m = map_hdf(hdf)
            self.gen_text(hdf, m)
            if 'axes' in m.arrays and not self.xaxis.get():
                self.xaxis.set(m.arrays['axes'])
            if 'signal' in m.arrays and not self.yaxis.get():
                self.yaxis.set(m.arrays['signal'])
            xvals, yvals = self.gen_xy(hdf, m)
            lab = os.path.basename(filepath)
            ln, = self.ax1.plot(xvals, yvals, label=lab)
            self.plot_list.append(ln)
        ttl = os.path.basename(filepath)
        self.ax1.set_title(ttl)
        self.update_plot()

    def gen_text(self, hdf_file, hdf_map=None):
        try:
            txt = format_hdf(hdf_file, self._text_expression, hdf_map, debug=False)
            self.textbox.configure(state=tk.NORMAL)
            self.textbox.delete('1.0', tk.END)
            self.textbox.insert('1.0', txt)
            self.textbox.configure(state=tk.DISABLED)
        except Exception as e:
            show_error(f"Error: {e}", parent=self.root)

    def edit_expression(self):
        """Double-click on text display => open config str"""
        try:
            self._text_expression = EditText(self._text_expression, self.root).show()
            self.update()
        except KeyError as ke:
            show_error(
                message=f"Item not recognised: {ke}",
                parent=self.root
            )

    def gen_xy(self, hdf_file, hdf_map=None):
        try:
            xvalues = eval_hdf(hdf_file, self.xaxis.get(), hdf_map)
            lenx = len(xvalues)
        except SyntaxError or NameError or TypeError:
            xvalues, lenx = [], 0
        try:
            yvalues = eval_hdf(hdf_file, self.yaxis.get(), hdf_map)
            leny = len(yvalues)
        except SyntaxError or NameError or TypeError:
            yvalues, leny = [], 0
        if lenx < leny:
            xvalues = range(leny)
        elif leny < lenx:
            yvalues = range(lenx)
        return xvalues, yvalues

    def reset_plot(self):
        self.ax1.set_xlabel(self.xaxis.get())
        self.ax1.set_ylabel(self.yaxis.get())
        self.ax1.set_title('')
        self.ax1.set_prop_cycle(None)  # reset colours
        self.ax1.legend([]).set_visible(False)
        for obj in self.plot_list:
            obj.remove()
        self.plot_list = []

    def update_plot(self):
        self.ax1.relim()
        self.ax1.autoscale(True)
        self.ax1.autoscale_view()
        self.fig.canvas.draw()
        self.toolbar.update()

    "======================================================"
    "================= event functions ===================="
    "======================================================"

    def update(self, event=None):
        self.load_file(self.filepath.get())

    def fun_xaxis(self):
        address = dataset_selector(self.filepath.get(), message='Select xaxis dataset', parent=self.root)
        if address:
            self.xaxis.set(address)
            self.update_plot()

    def fun_yaxis(self):
        address = dataset_selector(self.filepath.get(), message='Select yaxis dataset', parent=self.root)
        if address:
            self.yaxis.set(address)
            self.update_plot()

    def fun_default_xaxis(self):
        self.xaxis.set('')

    def fun_default_yaxis(self):
        self.yaxis.set('')

    def select_file(self):
        filepath = select_hdf_file(parent=self.root)
        if filepath:
            self.filepath.set(filepath)

    def fun_terminal(self, event=None):
        expression = self.terminal_entry.get()
        out_str = f"\n>>> {expression}\n"

        if ishdf(self.filepath.get()):
            try:
                with load_hdf(self.filepath.get()) as hdf:
                    out = eval_hdf(hdf, expression)
            except NameError as ne:
                out = ne
            out_str += f"{out}"
        else:
            out_str = "\n--- No file selected ---"
        self.terminal.configure(state=tk.NORMAL)
        self.terminal.insert(tk.END, out_str)
        self.terminal.see(tk.END)
        self.terminal.configure(state=tk.DISABLED)

    def fun_terminal_cls(self, event=None):
        self.terminal.delete('1.0', tk.END)

    def view_namespace(self, event=None):
        """Open HDFMapView on current file"""
        HDFMapView(self.filepath.get(), parent=self.root)

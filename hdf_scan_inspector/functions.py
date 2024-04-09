"""
HDF Scan Inspector - general functions

By Dan Porter
Diamond Light Source Ltd
2024
"""

import os
import datetime
import re
import tkinter as tk
from tkinter import filedialog, messagebox

import h5py


"==========================================================================="
"================================ HDF functions ============================"
"==========================================================================="


def address_name(address):
    """Convert hdf address to name"""
    name = os.path.basename(address)
    return os.path.basename(name) if name == 'value' else name


def display_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%a %d-%b-%Y %H:%M')


def list_files(folder_directory, extension='.nxs'):
    """Return list of files in directory with extension"""
    # return [os.path.join(folder_directory, file) for file in os.listdir(folder_directory) if file.endswith(extension)]
    return [file.path for file in os.scandir(folder_directory) if file.name.endswith(extension)]


def list_path_time_files(directory, extension='.nxs'):
    """Return [(path, modified_time(s), nfiles), ]"""
    # folders = [
    #     (f.path, f.stat().st_mtime, len(list_files(f.path, extension)))
    #     for f in os.scandir(directory) if f.is_dir()
    # ]  # this version might be slightly faster but doesn't handle permission errors
    folders = []
    for f in os.scandir(directory):
        if f.is_dir():
            try:
                folders.append((f.path, f.stat().st_mtime, len(list_files(f.path, extension))))
            except PermissionError:
                pass
    return folders


def get_hdf_value(hdf_filename, hdf_address, default_value=''):
    """Open HDF file and return value from single dataset"""
    with h5py.File(hdf_filename, 'r') as hdf:
        dataset = hdf.get(hdf_address)
        if isinstance(dataset, h5py.Dataset):
            if dataset.size > 1:
                return f"{dataset.dtype} {dataset.shape}"
            return dataset[()]
        return default_value


def map_hdf(hdf_file):
    """
    Create map of groups and datasets in HDF file

    Example:
        with h5py.File('somefile.nxs', 'r') as nx:
            map = map_hdf(nx)
        nxdata_address = map.classes['NXdata']
        start_time_address = map.values['start_time']
        eta_array_address = map.arrays['eta']
        detector_data_address = next(iter(map.image_data))

    :param hdf_file: hdf file object
    :return: HdfMap object with attributes:
        groups = {}  # stores attributes of each group by address
        classes = {}  # stores group addresses by nx_class
        datasets = {}  # stores attributes of each dataset by address
        arrays = {}  # stores array dataset addresses by name
        values = {}  # stores value dataset addresses by name
        image_data = {}  # stores dataset addresses of image data
    """

    class HdfMap:
        groups = {}  # stores attributes of each group by address
        classes = {}  # stores group addresses by nx_class
        datasets = {}  # stores attributes of each dataset by address
        arrays = {}  # stores array dataset addresses by name
        values = {}  # stores value dataset addresses by name
        combined = {}  # stores array and value addresses (arrays overwrite values)
        image_data = {}  # stores dataset addresses of image data
    hdf_map = HdfMap()

    def recur_func(hdf_group, top_address=''):
        for key in hdf_group:
            obj = hdf_group.get(key)
            link = hdf_group.get(key, getlink=True)
            address = top_address + '/' + key
            name = address_name(address)

            # Group
            if isinstance(obj, h5py.Group):
                try:
                    nx_class = obj.attrs['NX_class'].decode() if 'NX_class' in obj.attrs else 'Group'
                except AttributeError:
                    nx_class = obj.attrs['NX_class']
                except OSError:
                    nx_class = 'Group'  # if object doesn't have attrs
                hdf_map.groups[address] = (nx_class, name)
                if nx_class not in hdf_map.classes:
                    hdf_map.classes[nx_class] = address
                recur_func(obj, address)

            # Dataset
            elif isinstance(obj, h5py.Dataset) and not isinstance(link, h5py.SoftLink):
                hdf_map.datasets[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                if obj.ndim >= 3:
                    hdf_map.image_data[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                elif obj.ndim > 0:
                    hdf_map.arrays[name] = address
                else:
                    hdf_map.values[name] = address

    # map file
    recur_func(hdf_file)
    # create combined dict, arrays overwrite values with same name
    hdf_map.combined = {**hdf_map.values, **hdf_map.arrays}
    return hdf_map


def eval_hdf(hdf_file, expression, file_map=None):
    """
    Evaluate an expression using the namespace of the hdf file
    :param hdf_file: hdf file object
    :param expression: str expression to be evaluated
    :param file_map: HdfMap object from map_hdf()
    :return: eval(expression)
    """
    if file_map is None:
        file_map = map_hdf(hdf_file)
    check_naughty_eval(expression)
    varnames = re.findall(r'[a-zA-Z]\w*', expression)
    namespace = {
        var: hdf_file[file_map.combined[var]][()] for var in varnames if var in file_map.combined
    }
    return eval(expression, globals(), namespace)


def check_naughty_eval(eval_str):
    """
    Check str for naughty eval arguments such as os or import
    This is not foolproof.
    :param eval_str: str
    :return: pass or raise error
    """
    bad_names = ['import', 'os.', 'sys.']
    for bad in bad_names:
        if bad in eval_str:
            raise Exception('This operation is not allowed as it contains: "%s"' % bad)

"==========================================================================="
"============================== NeXus functions ============================"
"==========================================================================="


def get_nexus_axes_datasets(hdf_object):
    """
    Nexus compliant method of finding default plotting axes in hdf files
     - find "default" entry group in top File group
     - find "default" data group in entry
     - find "axes" attr in default data
     - find "signal" attr in default data
     - generate addresses of signal and axes
     if not nexus compliant, raises KeyError
    This method is very fast but only works on nexus compliant files
    :param hdf_object: open HDF file object, i.e. h5py.File(...)
    :return axes_datasets: list of dataset objects for axes
    :return signal_dataset: dataset object for plot axis
    """
    # From: https://manual.nexusformat.org/examples/python/plotting/index.html
    # find the default NXentry group
    nx_entry = hdf_object[
        hdf_object.attrs["default"] if "default" in hdf_object.attrs else next(iter(hdf_object.keys()))
    ]
    # find the default NXdata group
    nx_data = nx_entry[nx_entry.attrs["default"] if "default" in nx_entry.attrs else "measurement"]
    # find the axes field(s)
    if isinstance(nx_data.attrs["axes"], (str, bytes)):
        axes_datasets = [nx_data[nx_data.attrs["axes"]]]
    else:
        axes_datasets = [nx_data[_axes] for _axes in nx_data.attrs["axes"]]
    # find the signal field
    signal_dataset = nx_data[nx_data.attrs["signal"]]
    return axes_datasets, signal_dataset


def get_nexus_axes_address(hdf_filename):
    """
    Open a NeXus compliant file and return the default plot axes
    :param hdf_filename: str filename of hdf file
    :return axes_address: str hdf address of first x-axis dataset
    :return signal_address: str hdf address of y-axis dataset
    """
    with h5py.File(hdf_filename, 'r') as nx:
        try:
            axes_datasets, signal_dataset = get_nexus_axes_datasets(nx)
        except KeyError:
            return '', ''
        axes_address = axes_datasets[0].name
        signal_address = signal_dataset.name
    return axes_address, signal_address


"==========================================================================="
"============================= TKinter functions ==========================="
"==========================================================================="


def create_root(window_title, parent=None):
    """Create tkinter root obect"""
    if parent:
        root = tk.Toplevel(parent)
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


def open_close_all_tree(treeview, branch="", openstate=True):
    """Open or close all items in ttk.treeview"""
    treeview.item(branch, open=openstate)
    for child in treeview.get_children(branch):
        open_close_all_tree(treeview, child, openstate)  # recursively open children


def show_error(message, parent=None):
    """Display and raise error"""
    messagebox.showwarning(
        title="HDF File Error",
        message=message,
        parent=parent,
    )
    raise Exception(message)


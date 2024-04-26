"""
HDF Scan Inspector - general functions

By Dan Porter
Diamond Light Source Ltd
2024
"""

import os
import ast
import builtins
import datetime
import numpy as np
import h5py
from pathlib import Path

try:
    import hdf5plugin  # required for compressed data
except ImportError:
    print('Warning: hdf5plugin not available.')

# parameters
DEFAULT_ADDRESS = "entry1/scan_command"
EXTENSIONS = ['.nxs', '.hdf', '.hdf5', '.h5']
DEFAULT_EXTENSION = EXTENSIONS[0]
MAX_TEXTVIEW_SIZE = 1000
# parameters for eval
GLOBALS = {'np': np}
GLOBALS_NAMELIST = dir(builtins) + list(GLOBALS.keys())
ishdf = h5py.is_hdf5


"==========================================================================="
"================================ HDF functions ============================"
"==========================================================================="


def load_hdf(hdf_filename):
    return h5py.File(hdf_filename, 'r')


def address_name(address):
    """Convert hdf address to name"""
    if isinstance(address, bytes):
        address = address.decode('ascii')
    address = address.replace('.', '_')  # remove dots as cant be evaluated
    name = os.path.basename(address)
    return os.path.basename(name) if name == 'value' else name


def display_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%a %d-%b-%Y %H:%M')


def list_files(folder_directory, extension='.nxs'):
    """Return list of files in directory with extension, returning list of full file paths"""
    # return [os.path.join(folder_directory, file) for file in os.listdir(folder_directory) if file.endswith(extension)]
    return sorted(
        (file.path for file in os.scandir(folder_directory) if file.is_file() and file.name.endswith(extension)),
        key=lambda x: os.path.getmtime(x)
    )


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
            except PermissionError or FileNotFoundError:
                pass
    return folders


def get_hdf_value(hdf_filename, hdf_address, default_value=''):
    """Open HDF file and return value from single dataset"""
    with load_hdf(hdf_filename) as hdf:
        dataset = hdf.get(hdf_address)
        if isinstance(dataset, h5py.Dataset):
            if dataset.size > 1:
                return f"{dataset.dtype} {dataset.shape}"
            return dataset[()]
        return default_value


def hdfobj_string(hdf_filename, address):
    """Generate string describing object in hdf file"""
    with load_hdf(hdf_filename) as hdf:
        obj = hdf.get(address)
        try:
            link = repr(hdf.get(address, getlink=True))
        except RuntimeError:
            link = 'No link'
        myclass = hdf.get(address, getclass=True)
        out = f"{obj.name}\n"
        out += f"{repr(obj)}\n"
        out += f"{link}\n"
        out += f"{repr(myclass)}\n"
        out += '\nattrs:\n'
        out += '\n'.join([f"{key}: {obj.attrs[key]}" for key in obj.attrs])
        if isinstance(obj, h5py.Dataset):
            out += '\n\n--- Data ---\n'
            out += f"Shape: {obj.shape}\nSize: {obj.size}\nValues:\n"
            if obj.size > MAX_TEXTVIEW_SIZE:
                out += '---To large to view---'
            else:
                out += str(obj[()])
    return out


def search_filename_in_folder(topdir, search_str="*.nxs", case_sensitive=False):
    """
    Search recursivley for filenames
    :param topdir: str address of directory to start in
    :param search_str: str to search for, use * to specify unkonwn, e.g. "*.nxs"
    :param case_sensitive:
    :return: list
    """
    return [f.absolute() for f in Path(topdir).rglob(search_str, case_sensitive=case_sensitive)]


def search_hdf_files(topdir, search_str=None, extension=DEFAULT_EXTENSION, address=DEFAULT_ADDRESS,
                     whole_word=False, case_sensitive=False):
    """
    Search recurslively for hdf files in folder and check within files for dataset
    :param topdir: str address of directory to start in
    :param search_str: str or None, if None, returns any hdf file with this dataset
    :param extension: str extension of files, e.g. ".nxs"
    :param address: str dataset address to check
    :param whole_word: Bool
    :param case_sensitive:  Bool
    :return: list
    """
    output = []
    search_str = '' if search_str is None else search_str
    search_str = search_str if case_sensitive else search_str.lower()

    for f in Path(topdir).rglob(f"*{extension}"):
        if not h5py.is_hdf5(f):
            continue
        with load_hdf(f) as hdf:
            dataset = hdf.get(address)
            if dataset:
                if search_str:
                    value = str(dataset[()]) if case_sensitive else str(dataset[()]).lower()
                    if (whole_word and search_str == value) or (search_str in value):
                        output.append(f)
                else:
                    output.append(f)


"==========================================================================="
"============================== Image functions ============================"
"==========================================================================="


def dataset_shape(dataset):
    """
    Return 3D dataset shape, flattening any dimensions that aren't the last two
    :param dataset: HDF dataset object
    :return: (i,j,k) tuple
    """
    shape = (np.prod(dataset.shape[:-2]), *dataset.shape[-2:])
    return shape


def get_image(dataset, image_number, axis=0):
    """
    Load a single image from a dataset, on a given axis
    Assumes the dataset is 3D
    If dataset is >3D, dimensions [0:-2] will be flattened
    :param dataset: HDF dataset object with ndim > 2
    :param image_number: index of the dataset along given axis (flattened index if >3D)
    :param axis: 0,1,2 dataset axis
    :return: 2D numpy array
    """
    axis = axis % 3
    if axis == 0:
        # axis0 may be a combination of 1+ axes
        index_slice = np.unravel_index(image_number, dataset.shape[:-2]) + (slice(None), ) * 2
        shape = dataset.shape[-2:]
    elif axis == 1:
        index_slice = (slice(None), ) * len(dataset.shape[:-2]) + (image_number, ) + (slice(None), )
        shape = dataset_shape(dataset)
        shape = (shape[0], shape[2])
    else:
        index_slice = (slice(None),) * len(dataset.shape[:-2]) + (slice(None),) + (image_number,)
        shape = dataset_shape(dataset)
        shape = (shape[0], shape[1])
    return dataset[index_slice].reshape(shape)


def get_image_from_files(image_filenames, image_number, axis=0):
    """
    Load a single image from a list of image files (e.g. .tif)
    :param image_filenames: list of str
    :param image_number: int
    :param axis:
    :return:
    """
    from imageio import imread
    if axis == 0:
        # return single image
        return imread(image_filenames[image_number])
    if axis == 1:
        # return image of slice of each image
        return np.array([imread(f)[image_number, :] for f in image_filenames])
    return np.array([imread(f)[:, image_number] for f in image_filenames])


def get_hdf_image(hdf_filename, address, image_number, axis=0):
    """
    Load a single image from a dataset in a HDF file, on a given axis
    :param hdf_filename: str filename of HDF file
    :param address: str HDF address of 3D dataset
    :param image_number: index of the dataset along given axis (flattened index if >3D)
    :param axis: 0,1,2 dataset axis
    :return: 2D numpy array
    """
    with load_hdf(hdf_filename) as hdf:
        dataset = hdf.get(address)
        image = get_image(dataset, image_number, axis)
    return image


def get_hdf_array_value(hdf_filename, address, image_number):
    """
    Load a single value from a dataset in a HDF file
    :param hdf_filename: str filename of HDF file
    :param address: str HDF address of 3D dataset
    :param image_number: index of the dataset
    :return: float
    """
    with load_hdf(hdf_filename) as hdf:
        if not address:
            return 0
        dataset = hdf.get(address)
        if dataset and image_number < len(dataset):
            return dataset[image_number]
    return 0


def get_hdf_image_address(hdf_filename):
    """
    Return address of first 3D dataset in HDF file
    :param hdf_filename: str filename of hdf file
    :return: str hdf address or empty str
    """

    def recur_func(hdf_group, top_address='/'):
        for key in hdf_group:
            obj = hdf_group.get(key)
            address = top_address + key
            if isinstance(obj, h5py.Group):
                address = recur_func(obj, address + '/')
                if address:
                    return address
            elif isinstance(obj, h5py.Dataset) and obj.ndim >= 3:
                return address
        return ""

    with load_hdf(hdf_filename) as hdf:
        image_address = recur_func(hdf, "")
    return image_address


def check_image_dataset(hdf_filename, address):
    """
    Check dataset exists and is correct shape for image use
    :param hdf_filename: str filepath of HDF file
    :param address: str HDF address of dataset
    :return: str error messge, empty str if OK
    """
    if not hdf_filename:
        return "Please select a HDF file"
    if not h5py.is_hdf5(hdf_filename):
        return f"{hdf_filename} is not a HDF5 file"
    if not address:
        return "Please select a Dataset address"

    with load_hdf(hdf_filename) as hdf:
        dataset = hdf.get(address)
        if dataset is None:
            return f"HDF File:\n{hdf_filename}\n does not contain the dataset:\n{address}"
        if dataset.ndim < 3:
            return f"Dataset:\n{address}\n is the wrong shape: {dataset.shape}"
    return ""


"==========================================================================="
"=============================== EVAL functions ============================"
"==========================================================================="


def map_hdf(hdf_file):
    """
    Create map of groups and datasets in HDF file

    Example:
        with h5py.File('somefile.nxs', 'r') as nx:
            map = map_hdf(nx)
        nxdata_address = map.classes['NXdata'][0]
        start_time_address = map.values['start_time']
        eta_array_address = map.arrays['eta']
        detector_data_address = next(iter(map.image_data))

    :param hdf_file: hdf file object
    :return: HdfMap object with attributes:
        groups = {}  # stores attributes of each group by address
        classes = {}  # stores list of group addresses by nx_class
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

    # Defaults
    try:
        axes_datasets, signal_dataset = get_nexus_axes_datasets(hdf_file)
        if axes_datasets[0].name in hdf_file:
            hdf_map.arrays['axes'] = axes_datasets[0].name
        if signal_dataset.name in hdf_file:
            hdf_map.arrays['signal'] = signal_dataset.name
    except KeyError:
        pass

    def recur_func(hdf_group, top_address=''):
        for key in hdf_group:
            obj = hdf_group.get(key)
            link = hdf_group.get(key, getlink=True)
            address = top_address + '/' + key
            name = address_name(address)
            altname = address_name(obj.attrs['local_name']) if 'local_name' in obj.attrs else name

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
                    hdf_map.classes[nx_class] = [address]
                else:
                    hdf_map.classes[nx_class].append(address)
                recur_func(obj, address)

            # Dataset
            elif isinstance(obj, h5py.Dataset) and not isinstance(link, h5py.SoftLink):
                hdf_map.datasets[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                if obj.ndim >= 3:
                    hdf_map.image_data[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                    hdf_map.arrays[name] = address
                    hdf_map.arrays[altname] = address
                elif obj.ndim > 0:
                    hdf_map.arrays[name] = address
                    hdf_map.arrays[altname] = address
                else:
                    hdf_map.values[name] = address
                    hdf_map.values[altname] = address

    # map file
    recur_func(hdf_file)
    # Check array length - keep only arrays with the most common length
    array_sizes = [hdf_map.datasets[v][1] for k, v in hdf_map.arrays.items()]
    max_array = max(set(array_sizes), key=array_sizes.count)
    # max_array = max(hdf_map.datasets[v][1] for k, v in hdf_map.arrays.items())
    hdf_map.arrays = {k: v for k, v in hdf_map.arrays.items() if hdf_map.datasets[v][1] == max_array}
    # create combined dict, arrays overwrite values with same name
    hdf_map.combined = {**hdf_map.values, **hdf_map.arrays}
    return hdf_map


def find_varnames(expression):
    """Returns list of variable names in expression, ommiting builtins and globals"""
    # varnames = re.findall(r'[a-zA-Z]\w*', expression)
    return [node.id for node in ast.walk(ast.parse(expression, mode='eval'))
            if type(node) is ast.Name and node.id not in GLOBALS_NAMELIST]


def generate_namespace(hdf_file, name_address, varnames=None, default=np.array('--')):
    """
    Generate namespace dict

    Adds additional values if not in name_address dict:
        filename: str, name of hdf_file
        filepath: str, full path of hdf_file
        axes_address: str hdf address of default axes
        signal_address: str hdf address of default signal

    :param hdf_file: hdf file object
    :param name_address: dict[varname]='hdfaddress'
    :param varnames: list of str or None, if None, use generate all items in name_address
    :param default: any, if varname not in name_address - return default instead
    :return:
    """
    if varnames is None:
        varnames = list(name_address.keys())
    namespace = {name: hdf_file[name_address[name]][()] for name in varnames if name in name_address}
    defaults = {name: default for name in varnames if name not in name_address}
    # add extra params
    extras = {
        'filepath': hdf_file.filename if hasattr(hdf_file, 'filename') else 'unknown',
        'filename': address_name(hdf_file.filename) if hasattr(hdf_file, 'filename') else 'unknown',
        'axes_address': name_address['axes'] if 'axes' in name_address else 'None',
        'signal_address': name_address['signal'] if 'signal' in name_address else 'None'
    }
    return {**defaults, **extras, **namespace}


def eval_hdf(hdf_file, expression, file_map=None, debug=False):
    """
    Evaluate an expression using the namespace of the hdf file
    :param hdf_file: hdf file object
    :param expression: str expression to be evaluated
    :param file_map: HdfMap object from map_hdf()
    :param debug: bool, if True, returns additional info
    :return: eval(expression)
    """
    if expression in hdf_file:
        return hdf_file[expression][()]
    if file_map is None:
        file_map = map_hdf(hdf_file)
    check_naughty_eval(expression)
    varnames = [name for name in file_map.combined if name in expression]  # find varnames matching map
    varnames += find_varnames(expression)  # finds other varnames (not builtins)
    namespace = generate_namespace(hdf_file, file_map.combined, varnames)
    if debug:
        print(f"Expression: {expression}\nvarnames: {varnames}\nnamespace: {namespace}\n")
    return eval(expression, GLOBALS, namespace)


def format_hdf(hdf_file, expression, file_map=None, debug=False):
    """
    Evaluate a formatted string expression using the namespace of the hdf file
    :param hdf_file: hdf file object
    :param expression: str expression using {name} format specifiers
    :param file_map: HdfMap object from map_hdf()
    :param debug: bool, if True, returns additional info
    :return: expression.format(**namespace)
    """
    expression = 'f"""' + expression + '"""'  # convert to fstr
    return eval_hdf(hdf_file, expression, file_map, debug)


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


def get_strict_nexus_axes_datasets(hdf_object):
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
    nx_entry = hdf_object[hdf_object.attrs["default"]]
    # find the default NXdata group
    nx_data = nx_entry[nx_entry.attrs["default"]]
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
    with load_hdf(hdf_filename) as nx:
        try:
            axes_datasets, signal_dataset = get_nexus_axes_datasets(nx)
        except KeyError:
            return '', ''
        axes_address = axes_datasets[0].name
        signal_address = signal_dataset.name
    return axes_address, signal_address


"""
HDF Scan Inspector - general functions for HDF files

By Dan Porter
Diamond Light Source Ltd
2024
"""

import os
import ast
import builtins
import datetime
import pathlib
import typing
import numpy as np
import h5py

try:
    import hdf5plugin  # required for compressed data
except ImportError:
    print('Warning: hdf5plugin not available.')

# parameters
SEP = '/'  # HDF address separator
DEFAULT_ADDRESS = "entry1/scan_command"
EXTENSIONS = ['.nxs', '.hdf', '.hdf5', '.h5']
DEFAULT_EXTENSION = EXTENSIONS[0]
NX_LOCALNAME = 'local_name'
NX_SCAN_SHAPE_ADDRESS = 'entry1/scan_shape'
NX_SIGNAL = 'signal'
NX_AXES = 'axes'
MAX_TEXTVIEW_SIZE = 1000
# parameters for eval
GLOBALS = {'np': np}
GLOBALS_NAMELIST = dir(builtins) + list(GLOBALS.keys())
ishdf = h5py.is_hdf5


"==========================================================================="
"================================ HDF functions ============================"
"==========================================================================="


def load_hdf(hdf_filename: str) -> h5py.File:
    return h5py.File(hdf_filename, 'r')


def address_name(address: str | bytes) -> str:
    """Convert hdf address to name"""
    if hasattr(address, 'decode'):  # Byte string
        address = address.decode('ascii')
    address = address.replace('.', '_')  # remove dots as cant be evaluated
    name = address.split(SEP)[-1]
    return address.split(SEP)[-1] if name == 'value' else name


def display_timestamp(timestamp: float) -> str:
    return datetime.datetime.fromtimestamp(timestamp).strftime('%a %d-%b-%Y %H:%M')


def list_files(folder_directory: str, extension='.nxs') -> list[str]:
    """Return list of files in directory with extension, returning list of full file paths"""
    # return [os.path.join(folder_directory, file) for file in os.listdir(folder_directory) if file.endswith(extension)]
    try:
        return sorted(
            (file.path for file in os.scandir(folder_directory) if file.is_file() and file.name.endswith(extension)),
            key=lambda x: os.path.getmtime(x)
        )
    except (FileNotFoundError, PermissionError, OSError):
        return []


def list_path_time(directory: str) -> list[tuple[str, float]]:
    """
    Return list of folders in diectory, along with modified time
        [(path, modified_time(s), nfiles), ...] = list_path_time_files('/folder/path', '.nxs')
    :param directory: directory to look in
    :return: [(path, timestamp), ...]
    """
    folders = [('.', os.stat(directory).st_mtime)]
    for f in os.scandir(directory):
        if f.is_dir():
            try:
                folders.append((f.path, f.stat().st_mtime))
            except PermissionError or FileNotFoundError:
                pass
    return folders


def list_path_time_files(directory: str, extension='.nxs') -> list[tuple[str, float, int]]:
    """
    Return list of folders in diectory, along with modified time and number of contained files
        [(path, modified_time(s), nfiles), ...] = list_path_time_files('/folder/path', '.nxs')
    :param directory: directory to look in
    :param extension: file extension to list as nfiles
    :return: [(path, timestamp, nfiles), ...]
    """
    # folders = [
    #     (f.path, f.stat().st_mtime, len(list_files(f.path, extension)))
    #     for f in os.scandir(directory) if f.is_dir()
    # ]  # this version might be slightly faster but doesn't handle permission errors
    folders = [('.', os.stat(directory).st_mtime, len(list_files(directory, extension)))]
    for f in os.scandir(directory):
        if f.is_dir():
            try:
                folders.append((f.path, f.stat().st_mtime, len(list_files(f.path, extension))))
            except PermissionError or FileNotFoundError:
                pass
    return folders


def folder_summary(directory: str) -> str:
    """Generate summary of folder"""
    subdirs = list_path_time(directory)
    if len(subdirs) > 50:
        subdirs_str = f"{len(subdirs)-1} sub-directories"
    else:
        subdirs_str = '\n'.join(
            f"  {os.path.basename(path):30}: {display_timestamp(time)}" for path, time in subdirs
        )
    allfiles = list_files(directory, '')
    all_ext = {os.path.splitext(file)[-1] for file in allfiles}
    file_types = '\n'.join(f"  {ext}: {len([file for file in allfiles if file.endswith(ext)])}" for ext in all_ext)
    summary = (
        f"Folder: {os.path.abspath(directory)}\n" +
        f"Modified: {display_timestamp(os.stat(directory).st_mtime)}\n\n" +
        f"Sub-Directories:\n{subdirs_str}\n" +
        f"\nFiles: {len(allfiles)}\n"
        f"File-types:\n{file_types}"
    )
    return summary


def get_hdf_value(hdf_filename: str, hdf_address: str, default_value: typing.Any = '') -> typing.Any:
    """
    Open HDF file and return value from single dataset
    :param hdf_filename: str filename of hdf file
    :param hdf_address: str hdf address specifier of dataset
    :param default_value: Any - returned value if hdf_address is not available in file
    :return [dataset is array]: str "{type} {shape}"
    :return [dataset is not array]: output of dataset[()]
    :return [dataset doesn't exist]: default_value
    """
    try:
        with load_hdf(hdf_filename) as hdf:
            dataset = hdf.get(hdf_address)
            if isinstance(dataset, h5py.Dataset):
                if dataset.size > 1:
                    return f"{dataset.dtype} {dataset.shape}"
                return dataset[()]
    except Exception:
        return default_value


def hdfobj_string(hdf_filename: str, hdf_address: str) -> str:
    """Generate string describing object in hdf file"""
    with load_hdf(hdf_filename) as hdf:
        obj = hdf.get(hdf_address)
        try:
            link = repr(hdf.get(hdf_address, getlink=True))
        except RuntimeError:
            link = 'No link'
        myclass = hdf.get(hdf_address, getclass=True)
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


def search_filename_in_folder(topdir: str, search_str: str = "*.nxs", case_sensitive: bool = False):
    """
    Search recursivley for filenames
    :param topdir: str address of directory to start in
    :param search_str: str to search for, use * to specify unkonwn, e.g. "*.nxs"
    :param case_sensitive:
    :return: list
    """
    return [f.absolute() for f in pathlib.Path(topdir).rglob(search_str, case_sensitive=case_sensitive)]


def search_hdf_files(topdir: str, search_str: str | None = None, extension: str = DEFAULT_EXTENSION,
                     address: str = DEFAULT_ADDRESS, whole_word: bool = False,
                     case_sensitive: bool = False) -> list[str]:
    """
    Search recurslively for hdf files in folder and check within files for dataset
    :param topdir: str address of directory to start in
    :param search_str: str or None, if None, returns any hdf file with this dataset
    :param extension: str extension of files, e.g. ".nxs"
    :param address: str dataset address to check
    :param whole_word: search for whole words only
    :param case_sensitive: search is case-sensitive
    :return: list
    """
    output = []
    search_str = '' if search_str is None else search_str
    search_str = search_str if case_sensitive else search_str.lower()

    for f in pathlib.Path(topdir).rglob(f"*{extension}"):
        if not h5py.is_hdf5(f):
            continue
        with load_hdf(f.name) as hdf:
            dataset = hdf.get(address)
            if dataset:
                if search_str:
                    value = str(dataset[()]) if case_sensitive else str(dataset[()]).lower()
                    if (whole_word and search_str == value) or (search_str in value):
                        output.append(f.name)
                else:
                    output.append(f.name)
    return output


"==========================================================================="
"============================== Image functions ============================"
"==========================================================================="


def dataset_shape(dataset: h5py.Dataset) -> tuple[int, int, int]:
    """
    Return 3D dataset shape, flattening any dimensions that aren't the last two
    :param dataset: HDF dataset object
    :return: (i,j,k) tuple
    """
    shape = (np.prod(dataset.shape[:-2]), *dataset.shape[-2:])
    return shape


def get_image(dataset: h5py.Dataset, image_number: int, axis: int = 0) -> np.array:
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


def get_image_from_files(image_filenames: list[str], image_number: int, axis: int = 0) -> np.array:
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


def get_hdf_image(hdf_filename: str, address: str, image_number: int, axis: int = 0) -> np.array:
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


def get_hdf_array_value(hdf_filename: str, address: str, image_number: int) -> float | int:
    """
    Load a single value from a dataset in an HDF file
    :param hdf_filename: str filename of HDF file
    :param address: str HDF address of array dataset
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


def get_hdf_image_address(hdf_filename: str) -> str:
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


def check_image_dataset(hdf_filename: str, address: str) -> str:
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


class HdfMap2:
    """
    HdfMap object, container for addresses of different objects in an HDF file
        map = HdfMap(hdf_obj)

    *** HdfMap Attributes ***
    map.groups = {}  # stores attributes of each group by address
    map.classes = {}  # stores list of group addresses by nx_class
    map.datasets = {}  # stores attributes of each dataset by address
    map.arrays = {}  # stores array dataset addresses by name
    map.scannalbes = {}  # stores dataset addresses by name, where each dataset is the same size
    map.values = {}  # stores value dataset addresses by name
    map.image_data = {}  # stores dataset addresses of image data

    *** HdfMap Functions ***
    map.get_size('name' | 'address') -> returns size of dataset
    map.get_shape('name' | 'address') -> returns shape of dataset
    map.get_attrs('name' | 'address') -> returns dict of attributes of dataset
    map.get_attr('name' | 'address', attr_name) -> returns attribute of dataset
    map.get_class('NXclass') -> returns address of first HDFGroup with NXclass attribute
    map.get_class_datasets('NXclass') -> returns list of dataset addresses of first HDFGroup with NXclass attribute

    *** HdfMap Value Functions ***
    map.get(hdf_obj, 'name') -> returns value from dataset associated with 'name'
    map.eval(hdf_obj, 'expression') -> evaluates expresion using namespace
    map.format(hdf_obj, '{expression}') -> evaluates str format expression using namespace
    """
    _debug = False

    def __init__(self, hdf_file: h5py.File):
        self._filename = hdf_file.filename
        self._debuglog = lambda message: None
        self.groups = {}  # stores attributes of each group by address
        self.classes = {}  # stores group addresses by nx_class
        self.datasets = {}  # stores attributes of each dataset by address
        self.arrays = {}  # stores array dataset addresses by name
        self.values = {}  # stores value dataset addresses by name
        self.scannables = {}  # stores array dataset addresses with given size, by name
        self.combined = {}  # stores array and value addresses (arrays overwrite values)
        self.image_data = {}  # stores dataset addresses of image data

        # map file
        self._populate(hdf_file)
        # Genereate additional attributes
        self.generate_scannables(self.most_common_size())

    def __repr__(self):
        return f"HdfMap('{self._filename}')"

    def debug(self, state=True):
        """Turn debugging on"""
        self._debug = state
        if self._debug:
            self._debuglog = lambda message: print(message)
        else:
            self._debuglog = lambda message: None

    def _load_defaults(self, hdf_file):
        """Load Nexus default axes and signal"""
        try:
            axes_datasets, signal_dataset = get_nexus_axes_datasets(hdf_file)
            if axes_datasets[0].name in hdf_file:
                self.arrays[NX_AXES] = axes_datasets[0].name
                self._debuglog(f"DEFAULT axes: {axes_datasets[0].name}")
            if signal_dataset.name in hdf_file:
                self.arrays[NX_SIGNAL] = signal_dataset.name
                self._debuglog(f"DEFAULT signal: {signal_dataset.name}")
        except KeyError:
            pass

    def _populate(self, hdf_group: h5py.Group, top_address: str = '') -> None:
        for key in hdf_group:
            obj = hdf_group.get(key)
            link = hdf_group.get(key, getlink=True)
            address = top_address + SEP + key  # build hdf address - a cross-file unique identifier
            name = address_name(address)
            altname = address_name(obj.attrs['local_name']) if 'local_name' in obj.attrs else name
            self._debuglog(f"{address}  {name}, altname={altname}, link={repr(link)}")

            # Group
            if isinstance(obj, h5py.Group):
                try:
                    nx_class = obj.attrs['NX_class'].decode() if 'NX_class' in obj.attrs else 'Group'
                except AttributeError:
                    nx_class = obj.attrs['NX_class']
                except OSError:
                    nx_class = 'Group'  # if object doesn't have attrs
                self.groups[address] = (nx_class, name)
                if nx_class not in self.classes:
                    self.classes[nx_class] = [address]
                else:
                    self.classes[nx_class].append(address)
                self._debuglog(f"{address}  HDFGroup: {nx_class}")
                self._populate(obj, address)

            # Dataset
            elif isinstance(obj, h5py.Dataset) and not isinstance(link, h5py.SoftLink):
                self.datasets[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                if obj.ndim >= 3:
                    self.image_data[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                    self.arrays[name] = address
                    self.arrays[altname] = address
                    self._debuglog(f"{address}  HDFDataset: image_data & array {name, obj.size, obj.shape}")
                elif obj.ndim > 0:
                    self.arrays[name] = address
                    self.arrays[altname] = address
                    self._debuglog(f"{address}  HDFDataset: array {name, obj.size, obj.shape}")
                else:
                    self.values[name] = address
                    self.values[altname] = address
                    self._debuglog(f"{address}  HDFDataset: value")

    def most_common_size(self) -> int:
        """Return most common array size > 1"""
        array_sizes = [
            self.datasets[address][1]
            for name, address in self.arrays.items()
            if self.datasets[address][1] > 1
        ]
        return max(set(array_sizes), key=array_sizes.count)

    def most_common_shape(self) -> tuple:
        """Return most common non-singular array shape"""
        array_shapes = [
            self.datasets[address][2]
            for name, address in self.arrays.items()
            if len(self.datasets[address][2]) > 0
        ]
        return max(set(array_shapes), key=array_shapes.count)

    def generate_scannables(self, array_size) -> None:
        """Populate self.scannables field with datasets size that match array_size"""
        self.scannables = {k: v for k, v in self.arrays.items() if self.datasets[v][1] == array_size}
        # create combined dict, scannables and arrays overwrite values with same name
        self.combined = {**self.values, **self.arrays, **self.scannables}

    def _get_dataset(self, name_or_address: str, idx: int):
        """Return attribute of dataset"""
        if name_or_address in self.datasets:
            return self.datasets[name_or_address][idx]
        if name_or_address in self.combined:
            return self.datasets[self.combined[name_or_address]][idx]

    def get_size(self, name_or_address: str) -> int:
        """Return size of dataset"""
        return self._get_dataset(name_or_address, 1)

    def get_shape(self, name_or_address: str) -> tuple:
        """Return shape of dataset"""
        return self._get_dataset(name_or_address, 2)

    def get_attrs(self, name_or_address: str) -> dict:
        """Return attributes of dataset"""
        return self._get_dataset(name_or_address, 3)

    def get_attr(self, name_or_address: str, attr_label: str, default: str = '') -> str:
        """Return named attribute from dataset, or default"""
        attrs = self.get_attrs(name_or_address)
        if attr_label in attrs:
            return attrs[attr_label]
        return default

    def get_class(self, nx_class: str) -> str | None:
        """Return HDF address of first group with nx_class attribute"""
        if nx_class in self.classes:
            return self.classes[nx_class][0]

    def get_class_datasets(self, nx_class: str) -> list[str] | None:
        """Return list of HDF dataset addresses from first group with nx_class attribute"""
        class_address = self.get_class(nx_class)
        if class_address:
            return [address for address in self.datasets if address.startswith(class_address)]

    def get(self, hdf_file: h5py.File, name_or_address: str, default: typing.Any = None) -> typing.Any:
        """
        Evaluate an expression using the namespace of the hdf file
        :param hdf_file: hdf file object
        :param name_or_address: str name of dataset
        :param default: if name not in self.combined, return default
        :return: hdf[dataset/address/name][()]
        """
        if name_or_address in self.datasets:
            return hdf_file[name_or_address][()]
        if name_or_address in self.combined:
            address = self.combined[name_or_address]
            return hdf_file[address][()]
        return default

    def eval(self, hdf_file: h5py.File, expression: str, debug: bool = False) -> typing.Any:
        """
        Evaluate an expression using the namespace of the hdf file
        :param hdf_file: hdf file object
        :param expression: str expression to be evaluated
        :param debug: bool, if True, returns additional info
        :return: eval(expression)
        """
        return eval_hdf(hdf_file, expression, self, debug=debug)

    def format(self, hdf_file: h5py.File, expression: str, debug: bool = False) -> str:
        """
        Evaluate a formatted string expression using the namespace of the hdf file
        :param hdf_file: hdf file object
        :param expression: str expression using {name} format specifiers
        :param debug: bool, if True, returns additional info
        :return: eval_hdf(f"expression")
        """
        return format_hdf(hdf_file, expression, self, debug=debug)


class HdfMap:
    """
    HdfMap object, container for addresses of different objects in an HDF file
        map = HdfMap()
    map.groups = {}  # stores attributes of each group by address
    map.classes = {}  # stores list of group addresses by nx_class
    map.datasets = {}  # stores attributes of each dataset by address
    map.arrays = {}  # stores array dataset addresses by name
    map.scannalbes = {}  # stores dataset addresses by name, where each dataset is the same size
    map.values = {}  # stores value dataset addresses by name
    map.image_data = {}  # stores dataset addresses of image data
    """
    def __init__(self):
        self.groups = {}  # stores attributes of each group by address
        self.classes = {}  # stores group addresses by nx_class
        self.datasets = {}  # stores attributes of each dataset by address
        self.arrays = {}  # stores array dataset addresses by name
        self.values = {}  # stores value dataset addresses by name
        self.combined = {}  # stores array and value addresses (arrays overwrite values)
        self.image_data = {}  # stores dataset addresses of image data

    def get(self, hdf_file: h5py.File, name: str, default: typing.Any = None) -> typing.Any:
        """
        Evaluate an expression using the namespace of the hdf file
        :param hdf_file: hdf file object
        :param name: str name of dataset
        :param default: if name not in self.combined, return default
        :return: hdf[dataset/address/name][()]
        """
        if name in self.combined:
            address = self.combined[name]
            return hdf_file[address][()]
        return default

    def eval(self, hdf_file: h5py.File, expression: str, debug: bool = False) -> typing.Any:
        """
        Evaluate an expression using the namespace of the hdf file
        :param hdf_file: hdf file object
        :param expression: str expression to be evaluated
        :param debug: bool, if True, returns additional info
        :return: eval(expression)
        """
        return eval_hdf(hdf_file, expression, self, debug=debug)

    def format(self, hdf_file: h5py.File, expression: str, debug: bool = False) -> str:
        """
        Evaluate a formatted string expression using the namespace of the hdf file
        :param hdf_file: hdf file object
        :param expression: str expression using {name} format specifiers
        :param debug: bool, if True, returns additional info
        :return: eval_hdf(f"expression")
        """
        return format_hdf(hdf_file, expression, self, debug=debug)


def map_hdf(hdf_file: h5py.File, debug: bool = False) -> HdfMap:
    """
    Create map of groups and datasets in HDF file

    Example:
        with h5py.File('somefile.nxs', 'r') as nx:
            map = map_hdf(nx)
        nxdata_address = map.classes['NXdata'][0]
        start_time_address = map.values['start_time']
        eta_array_address = map.arrays['eta']
        detector_data_address = next(iter(map.image_data))

    Special parameters:
        map.arrays['axes'] << returns the address of the first default 'axes' attribute
        map.arrays['signal'] << returns the address of the default 'signal' attribute

    Arrays:
        map.arrays = {'name': 'hdf_address'}
        map.arrays is populated by hdf datasets addresses with >0 dimensions and
        a length equal to the most common dataset.size in the file

    :param hdf_file: hdf file object
    :param debug: prints debugging if True
    :return: HdfMap object with attributes:
        groups = {}  # stores attributes of each group by address
        classes = {}  # stores list of group addresses by nx_class
        datasets = {}  # stores attributes of each dataset by address
        arrays = {}  # stores array dataset addresses by name
        values = {}  # stores value dataset addresses by name
        image_data = {}  # stores dataset addresses of image data
    """
    hdf_map = HdfMap()

    # Debugging
    if debug:
        def debuglog(message):
            print(message)
    else:
        def debuglog(message):
            pass

    # Defaults
    try:
        axes_datasets, signal_dataset = get_nexus_axes_datasets(hdf_file)
        if axes_datasets[0].name in hdf_file:
            hdf_map.arrays[NX_AXES] = axes_datasets[0].name
            debuglog(f"DEFAULT axes: {axes_datasets[0].name}")
        if signal_dataset.name in hdf_file:
            hdf_map.arrays[NX_SIGNAL] = signal_dataset.name
            debuglog(f"DEFAULT signal: {signal_dataset.name}")
    except KeyError:
        pass

    def recur_func(hdf_group, top_address=''):
        for key in hdf_group:
            obj = hdf_group.get(key)
            link = hdf_group.get(key, getlink=True)
            address = top_address + SEP + key  # build hdf address - a cross-file unique identifier
            name = address_name(address)
            altname = address_name(obj.attrs['local_name']) if 'local_name' in obj.attrs else name
            debuglog(f"{address}  {name}, altname={altname}, link={repr(link)}")

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
                debuglog(f"{address}  HDFGroup: {nx_class}")
                recur_func(obj, address)

            # Dataset
            elif isinstance(obj, h5py.Dataset) and not isinstance(link, h5py.SoftLink):
                hdf_map.datasets[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                if obj.ndim >= 3:
                    hdf_map.image_data[address] = (name, obj.size, obj.shape, dict(obj.attrs))
                    hdf_map.arrays[name] = address
                    hdf_map.arrays[altname] = address
                    debuglog(f"{address}  HDFDataset: image_data & array {name, obj.size, obj.shape}")
                elif obj.ndim > 0:
                    hdf_map.arrays[name] = address
                    hdf_map.arrays[altname] = address
                    debuglog(f"{address}  HDFDataset: array {name, obj.size, obj.shape}")
                else:
                    hdf_map.values[name] = address
                    hdf_map.values[altname] = address
                    debuglog(f"{address}  HDFDataset: value")

    # map file
    recur_func(hdf_file)
    # Check array length - keep only arrays with the most common length
    array_sizes = [hdf_map.datasets[v][1] for k, v in hdf_map.arrays.items()]
    max_array = max(set(array_sizes), key=array_sizes.count)
    # max_array = max(hdf_map.datasets[v][1] for k, v in hdf_map.arrays.items())
    hdf_map.scannables = {k: v for k, v in hdf_map.arrays.items() if hdf_map.datasets[v][1] == max_array}
    # create combined dict, scannables and arrays overwrite values with same name
    hdf_map.combined = {**hdf_map.values, **hdf_map.arrays, **hdf_map.scannables}
    return hdf_map


def find_varnames(expression: str) -> list[str]:
    """Returns list of variable names in expression, ommiting builtins and globals"""
    # varnames = re.findall(r'[a-zA-Z]\w*', expression)
    return [node.id for node in ast.walk(ast.parse(expression, mode='eval'))
            if type(node) is ast.Name and node.id not in GLOBALS_NAMELIST]


def generate_namespace(hdf_file: h5py.File, name_address: dict[str, str], varnames: list[str] | None = None,
                       default: typing.Any = np.array('--')) -> dict[str, typing.Any]:
    """
    Generate namespace dict - create a dictionary linking the name of a dataset to the dataset value

    Adds additional values if not in name_address dict:
        filename: str, name of hdf_file
        filepath: str, full path of hdf_file
        _*name*: str hdf address of *name*

    :param hdf_file: hdf file object
    :param name_address: dict[varname]='hdfaddress'
    :param varnames: list of str or None, if None, use generate all items in name_address
    :param default: any, if varname not in name_address - return default instead
    :return: dict {'name': value, '_name': '/hdf/address'}
    """
    if varnames is None:
        varnames = list(name_address.keys())
    namespace = {name: hdf_file[name_address[name]][()] for name in varnames if name in name_address}
    defaults = {name: default for name in varnames if name not in name_address}
    addresses = {'_' + name: name_address[name] for name in varnames if name in name_address}
    # add extra params
    extras = {
        'filepath': hdf_file.filename if hasattr(hdf_file, 'filename') else 'unknown',
        'filename': os.path.basename(hdf_file.filename) if hasattr(hdf_file, 'filename') else 'unknown',
    }
    return {**defaults, **extras, **addresses, **namespace}


def eval_hdf(hdf_file: h5py.File, expression: str, file_map: HdfMap | None = None, debug: bool = False) -> typing.Any:
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


def format_hdf(hdf_file: h5py.File, expression: str, file_map: HdfMap | None = None, debug: bool = False) -> str:
    """
    Evaluate a formatted string expression using the namespace of the hdf file
    :param hdf_file: hdf file object
    :param expression: str expression using {name} format specifiers
    :param file_map: HdfMap object from map_hdf()
    :param debug: bool, if True, returns additional info
    :return: eval_hdf(f"expression")
    """
    expression = 'f"""' + expression + '"""'  # convert to fstr
    return eval_hdf(hdf_file, expression, file_map, debug)


def check_naughty_eval(eval_str: str) -> None:
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


def get_nexus_axes_datasets(hdf_object: h5py.File) -> tuple[list[h5py.Dataset], h5py.Dataset]:
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


def get_strict_nexus_axes_datasets(hdf_object: h5py.File) -> tuple[list[h5py.Dataset], h5py.Dataset]:
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


def get_nexus_axes_address(hdf_filename: str) -> tuple[str, str]:
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


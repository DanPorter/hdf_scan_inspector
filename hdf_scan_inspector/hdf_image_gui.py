"""
HDF Scan Inspector - Image GUI

By Dan Porter
Diamond Light Source Ltd
2024
"""

import h5py
import numpy as np
from imageio import imread
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk as NavigationToolbar2TkAgg
import sv_ttk

from hdf_scan_inspector.hdf_tree_gui import dataset_selector, HDFViewer
from hdf_scan_inspector.functions import create_root, topmenu, select_hdf_file, show_error, address_name, \
    get_nexus_axes_address

FIGURE_SIZE = [14, 6]
AXES = ['axis 1', 'axis 2', 'axis 3']
COLORMAPS = ['viridis', 'Spectral', 'plasma', 'inferno', 'Greys', 'Blues', 'winter', 'autumn',
             'hot', 'hot_r', 'hsv', 'rainbow', 'jet', 'twilight', 'hsv']
DEFAULT_COLORMAP = 'twilight'


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
    with h5py.File(hdf_filename, 'r') as hdf:
        dataset = hdf.get(address)
        image = get_image(dataset, image_number, axis)
    return image


def get_hdf_value(hdf_filename, address, image_number):
    """
    Load a single value from a dataset in a HDF file
    :param hdf_filename: str filename of HDF file
    :param address: str HDF address of 3D dataset
    :param image_number: index of the dataset
    :return: float
    """
    with h5py.File(hdf_filename, 'r') as hdf:
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

    with h5py.File(hdf_filename, 'r') as hdf:
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

    with h5py.File(hdf_filename, 'r') as hdf:
        dataset = hdf.get(address)
        if dataset is None:
            return f"HDF File:\n{hdf_filename}\n does not contain the dataset:\n{address}"
        if dataset.ndim < 3:
            return f"Dataset:\n{address}\n is the wrong shape: {dataset.shape}"
    return ""


class HDFImageViewer:
    """
    HDF Image Viewer - display a 3+D dataset as a series of images
    Usage:
        HDFViewer("hdf_file.hdf")
    Select a dataset address (one will be choosen by default)
    Use the displayed slider and options to view the data

    :param hdf_filename: str filename of HDF file
    :param figure_dpi: int describes the default size of the GUI
    """

    def __init__(self, hdf_filename="", figure_dpi=100, parent=None):

        self.root = create_root('HDF Image Viewer', parent=parent)

        # Variables
        self.filepath = tk.StringVar(self.root, hdf_filename)
        self.address = tk.StringVar(self.root, '')
        self.axis_address = tk.StringVar(self.root, '')
        self.error_message = ""
        self._ax = 0
        self._x_axis = 1
        self._y_axis = 2
        self.view_axis = tk.StringVar(self.root, AXES[self._ax])
        self.view_index = tk.IntVar(self.root, 0)
        self.axis_name = tk.StringVar(self.root, 'axis = ')
        self.axis_value = tk.DoubleVar(self.root, 0)
        self.add_phase = tk.DoubleVar(self.root, 0)
        self.logplot = tk.BooleanVar(self.root, False)
        self.difplot = tk.BooleanVar(self.root, False)
        self.mask = tk.DoubleVar(self.root, 0)
        self.cmin = tk.DoubleVar(self.root, 0)
        self.cmax = tk.DoubleVar(self.root, 1)
        self.fixclim = tk.BooleanVar(self.root, False)
        self.colormap = tk.StringVar(self.root, DEFAULT_COLORMAP)

        "----------- MENU -----------"
        menu = {
            'File': {
                'Select File': self.select_file,
                'New instance': self.menu_newinstance,
                'HDF Tree viewer': self.menu_treeviewer,
                'Reload': self.loadfile,
            },
            'Theme': {
                'Dark': sv_ttk.use_dark_theme,
                'Light': sv_ttk.use_light_theme,
                'Make small': self.menu_makesmall,
            }
        }

        topmenu(self.root, menu)

        "----------- Browse -----------"
        self.ini_browse()

        "----------- Dataset -----------"
        self.ini_dataset()
        self.ini_xaxis()

        "----------- Options -----------"
        self.ini_options()

        "----------- Slider -----------"
        self.tkscale = self.ini_slider()

        "----------- Image -----------"
        self.fig, self.ax1, self.ax1_image, self.cb1, self.toolbar = self.ini_image(figure_dpi)

        "-------- Start Mainloop ------"
        if hdf_filename:
            self._loadfile(hdf_filename)
        if parent is None:
            sv_ttk.use_light_theme()
            self.root.mainloop()

    "======================================================"
    "================= init functions ====================="
    "======================================================"

    def ini_browse(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='File', command=self.select_file)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.filepath)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        var.bind('<Return>', self.loadfile)
        var.bind('<KP_Enter>', self.loadfile)

    def ini_dataset(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)

        var = ttk.Button(frm, text='Image Dataset', command=self.select_dataset)
        var.pack(side=tk.LEFT)

        var = ttk.Entry(frm, textvariable=self.address)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

    def ini_xaxis(self):
        frm = ttk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        var = ttk.Button(frm, text='Value Dataset', command=self.select_axis_dataset)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.axis_address)
        var.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)

    def ini_options(self):
        frm = ttk.LabelFrame(self.root, text='Options', relief=tk.RIDGE)
        frm.pack(expand=tk.NO, pady=2, padx=5)

        var = ttk.Checkbutton(frm, text='Log', variable=self.logplot, command=self.update_image)
        var.pack(side=tk.LEFT, padx=6)
        var = ttk.Checkbutton(frm, text='Diff', variable=self.difplot, command=self.update_image)
        var.pack(side=tk.LEFT, padx=6)

        var = ttk.Label(frm, text='Mask <')
        var.pack(side=tk.LEFT, expand=tk.NO, padx=6)
        var = ttk.Entry(frm, textvariable=self.mask, width=6)
        var.pack(side=tk.LEFT, padx=6)
        var.bind('<Return>', self.update_image)
        var.bind('<KP_Enter>', self.update_image)

        var = ttk.OptionMenu(frm, self.colormap, *COLORMAPS, command=self.update_image)
        var.pack(side=tk.LEFT)

        var = ttk.Label(frm, text='clim:')
        var.pack(side=tk.LEFT, expand=tk.NO)
        var = ttk.Entry(frm, textvariable=self.cmin, width=6)
        var.pack(side=tk.LEFT)
        var.bind('<Return>', self.update_image)
        var.bind('<KP_Enter>', self.update_image)
        var = ttk.Entry(frm, textvariable=self.cmax, width=6)
        var.pack(side=tk.LEFT)
        var.bind('<Return>', self.update_image)
        var.bind('<KP_Enter>', self.update_image)
        var = ttk.Checkbutton(frm, text='Fix', variable=self.fixclim)
        var.pack(side=tk.LEFT)

    def ini_slider(self):
        frm = ttk.Frame(self.root)
        frm.pack(expand=tk.NO, pady=2, padx=5)

        var = ttk.OptionMenu(frm, self.view_axis, None, *AXES, command=self.update_axis)
        var.pack(side=tk.LEFT)

        def inc():
            self.view_index.set(self.view_index.get() + 1)
            self.update_image()

        def dec():
            self.view_index.set(self.view_index.get() - 1)
            self.update_image()

        var = ttk.Label(frm, text='Index:', width=8)
        var.pack(side=tk.LEFT)
        var = ttk.Button(frm, text='-', command=dec)
        var.pack(side=tk.LEFT)
        tkscale = ttk.Scale(frm, from_=0, to=100, variable=self.view_index, orient=tk.HORIZONTAL,
                            command=self.update_image, length=300)
        # var.bind("<ButtonRelease-1>", callback)
        tkscale.pack(side=tk.LEFT, expand=tk.YES)
        var = ttk.Button(frm, text='+', command=inc)
        var.pack(side=tk.LEFT)
        var = ttk.Entry(frm, textvariable=self.view_index, width=6)
        var.pack(side=tk.LEFT)
        var.bind('<Return>', self.update_image)
        var.bind('<KP_Enter>', self.update_image)

        # axis label
        var = ttk.Label(frm, textvariable=self.axis_name)
        var.pack(side=tk.LEFT)
        var = ttk.Label(frm, textvariable=self.axis_value)
        var.pack(side=tk.LEFT)
        return tkscale

    def ini_image(self, figure_dpi):
        fig = Figure(figsize=FIGURE_SIZE, dpi=figure_dpi)
        fig.patch.set_facecolor('w')
        # Amplitude
        ax1 = fig.add_subplot(111)
        ax1_image = ax1.pcolormesh(np.zeros([100, 100]), shading='auto')
        ax1.set_xlabel(u'Axis 0')
        ax1.set_ylabel(u'Axis 1')
        # ax1.set_title('Magnitudes')
        ax1.set_xlim([0, 100])
        ax1.set_ylim([0, 100])
        cb1 = fig.colorbar(ax1_image, ax=ax1)
        ax1.axis('image')

        frm = tk.Frame(self.root)
        frm.pack(expand=tk.YES, fill=tk.BOTH, pady=2, padx=5)
        canvas = FigureCanvasTkAgg(fig, frm)
        canvas.get_tk_widget().configure(bg='black')
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=2)

        # Toolbar
        frm = tk.Frame(self.root)
        frm.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH, padx=5, pady=2)
        toolbar = NavigationToolbar2TkAgg(canvas, frm)
        toolbar.update()
        toolbar.pack(fill=tk.X, expand=tk.YES)
        return fig, ax1, ax1_image, cb1, toolbar

    "======================================================"
    "================= menu functions ====================="
    "======================================================"

    def menu_newinstance(self):
        HDFImageViewer(self.filepath.get(), parent=self.root)

    def menu_treeviewer(self):
        HDFViewer(self.filepath.get(), parent=self.root)

    def menu_makesmall(self):
        print(f"size: {self.fig.get_size_inches()}, dpi: {self.fig.get_dpi()}")
        # self.fig.set_size_inches(6, 4)
        self.fig.set_dpi(50)
        self.fig.canvas.draw()

    "======================================================"
    "================ general functions ==================="
    "======================================================"

    def _loadfile(self, filename):
        """Load HDF file"""
        self.filepath.set(filename)
        image_address = get_hdf_image_address(filename)
        self.address.set(image_address)
        axes_address, signal_address = get_nexus_axes_address(filename)
        self.axis_address.set(axes_address)
        if not image_address:
            self.error_message = "Can't find an image address"
            show_error(self.error_message, self.root)
        self.update_axis()

    def _update_axis(self):
        """Get data size etc"""
        self._ax = int(self.view_axis.get()[-1]) - 1  # e.g. 'axis 1'

        hdf_filename = self.filepath.get()
        address = self.address.get()
        axis_address = self.axis_address.get()
        # Check dataset
        self.error_message = check_image_dataset(hdf_filename, address)
        if self.error_message:
            show_error(self.error_message, self.root)
        # Load image to get size and shape
        with h5py.File(hdf_filename, 'r') as hdf:
            dataset = hdf.get(address)

            shape = dataset_shape(dataset)
            if not self.fixclim.get():
                image = get_image(
                    dataset=dataset,
                    image_number=shape[self._ax]//2,
                    axis=self._ax
                )
                image_mean = np.mean(image[image > 0])
                image_max = np.max(image)
                cmax = image_mean + (image_max - image_mean) ** 0.7
                cmax = float(f"{cmax: .2g}")
                self.cmin.set(0)
                self.cmax.set(cmax)

            # axis values
            if axis_address:
                axis_dataset = hdf.get(axis_address)
                if axis_dataset and len(axis_dataset) == shape[self._ax]:
                    self.axis_name.set(f"{address_name(axis_address)} = ")
                    self.axis_value.set(axis_dataset[shape[self._ax]//2])

        # udpate scale and axes
        self.tkscale.config(to=shape[self._ax] - 1)  # set slider max
        if self._ax == 0:
            self.ax1.set_xlabel(u'Axis 3')
            self.ax1.set_ylabel(u'Axis 2')
            self.ax1.set_xlim([0, shape[2]])
            self.ax1.set_ylim([0, shape[1]])
        elif self._ax == 1:
            self.ax1.set_xlabel(u'Axis 3')
            self.ax1.set_ylabel(u'Axis 1')
            self.ax1.set_xlim([0, shape[2]])
            self.ax1.set_ylim([0, shape[0]])
        else:
            self.ax1.set_xlabel(u'Axis 2')
            self.ax1.set_ylabel(u'Axis 1')
            self.ax1.set_xlim([0, shape[1]])
            self.ax1.set_ylim([0, shape[0]])
        self.view_index.set(shape[self._ax]//2)

    def update_image(self, event=None):
        """Plot image data"""
        if self.error_message:
            show_error(self.error_message, self.root)
        # Load image
        image = get_hdf_image(
            hdf_filename=self.filepath.get(),
            address=self.address.get(),
            image_number=int(self.view_index.get()),
            axis=self._ax
        )
        # Options
        cmin, cmax = self.cmin.get(), self.cmax.get()
        if self.logplot.get():
            image = np.log10(image)
            cmax = np.log10(cmax)
        if self.difplot.get():
            raise Warning('Not implemented yet')
        if self.mask.get():
            raise Warning('Not implemented yet')
        # Add plot
        self.ax1_image.remove()
        colormap = self.colormap.get()
        clim = [cmin, cmax]
        self.ax1_image = self.ax1.pcolormesh(image, shading='auto', clim=clim, cmap=colormap)
        self.ax1_image.set_clim(clim)
        self.cb1.update_normal(self.ax1_image)
        self.toolbar.update()
        self.fig.canvas.draw()
        # Load axis label
        value = get_hdf_value(
            hdf_filename=self.filepath.get(),
            address=self.axis_address.get(),
            image_number=int(self.view_index.get())
        )
        self.axis_value.set(value)

    "======================================================"
    "================= event functions ===================="
    "======================================================"

    def loadfile(self, event=None):
        self._loadfile(self.filepath.get())

    def update_axis(self, event=None):
        """Get data size etc"""
        self._update_axis()
        self.update_image()

    "======================================================"
    "================ button functions ===================="
    "======================================================"

    def select_file(self, event=None):
        filename = select_hdf_file(self.root)
        if filename:
            self._loadfile(filename)

    def select_dataset(self):
        if self.filepath.get():
            address = dataset_selector(
                hdf_filename=self.filepath.get(),
                message="Select image data Dataset",
                parent=self.root,
            )
            if address:
                self.address.set(address)
                self.update_axis()

    def select_axis_dataset(self):
        if self.filepath.get():
            address = dataset_selector(
                hdf_filename=self.filepath.get(),
                message="Select axis data Dataset",
                parent=self.root,
            )
            if address:
                self.axis_address.set(address)
                self.update_axis()




"""
HDF Scan Inspector - example script

By Dan Porter
Diamond Light Source Ltd
2024
"""

from hdf_scan_inspector import HDFViewer, dataset_selector

# HDF_FILE = "C:/Users/grp66007/OneDrive - Diamond Light Source Ltd/I16/Nexus_Format/example_nexus/909400.nxs"
HDF_FILE = "C:/Users/grp66007/OneDrive - Diamond Light Source Ltd/I16/Nexus_Format/example_nexus/879486.nxs"

# Open HDFViewer GUI
# HDFViewer(HDF_FILE)

# Use dataset selector gui to select dataset address
# address = dataset_selector(HDF_FILE, 'Select a dataset')
# print(address)

from hdf_scan_inspector.hdf_image_gui import HDFImageViewer

HDFImageViewer(HDF_FILE)


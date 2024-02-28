"""
HDF Scan Inspector

By Dan Porter
Diamond Light Source Ltd
2024
"""

if __name__ == '__main__':

    import sys
    import h5py
    from hdf_scan_inspector import __version__, __date__, HDFViewer

    print('\nHDF Scan Inspector, version %s, %s\n By Dan Porter, Diamond Light Source Ltd.' % (__version__, __date__))

    filename = sys.argv[-1] if h5py.is_hdf5(sys.argv[-1]) else None
    HDFViewer(filename)

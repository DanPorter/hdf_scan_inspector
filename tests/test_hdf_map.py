"""
unit test
"""

import h5py
import hdf_scan_inspector.hdf_functions as fn

f = r"C:\Users\grp66007\OneDrive - Diamond Light Source Ltd\I16\Nexus_Format\example_nexus\1040323.nxs"
f2 = r"C:\Users\grp66007\OneDrive - Diamond Light Source Ltd\I16\Nexus_Format\example_nexus\1042049.nxs"
f3 = r"C:\Users\grp66007\OneDrive - Diamond Light Source Ltd\I16\Nexus_Format\I13_example\i13-1-368910.nxs"

print(f'\nFile1: {f}')
with h5py.File(f, 'r') as hdf:
    m = fn.map_hdf(hdf)
    out = fn.eval_hdf(hdf, 'np.sum(h)*a', file_map=m, debug=True)
    out2 = fn.eval_hdf(hdf, 'sum(total)', file_map=m, debug=True)

print(m.arrays)
print(out)
print(out2)

print(f'\n\nFile2: {f2}')
with h5py.File(f2, 'r') as hdf:
    m = fn.map_hdf(hdf)
    out = fn.eval_hdf(hdf, 'np.sum(sum)', file_map=m, debug=True)

print(m.arrays)
print(out)

print(f'\n\nFile3: {f3}')
with h5py.File(f3, 'r') as hdf:
    m = fn.map_hdf(hdf)

print(m.arrays)


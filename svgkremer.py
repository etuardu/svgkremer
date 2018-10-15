#!/usr/bin/env python3
import zipfile
import tempfile
import re
import mmap

kmz = "../gadm36_IND_0.kmz"
circles_amount = 1000

def zgrep(filename, regex):
    """Yields every match like zgrep -o"""
    with tempfile.TemporaryDirectory() as tempdir:
        zf = zipfile.ZipFile(filename)
        path = zf.extract(zf.filelist[0], tempdir)
        with open(path, 'r+') as f:
            data = mmap.mmap(f.fileno(), 0)
            for match in re.finditer(regex, data):
                yield match.group().decode("utf8")


with tempfile.TemporaryFile(
    mode='w+',
    encoding='utf-8') as coords_file:

    count = 0
    for c in zgrep(kmz, b"-?[0-9]+.[0-9]+,-?[0-9]+.[0-9]+"):
        # write each coordinate in the temp file,
        # get the count of how many coordinates we have
        coords_file.write(c+"\n")
        count += 1

    vmin = [float('+inf')]*2
    vmax = [float('-inf')]*2
    coords_file.seek(0) # rewind temp file
    for c in coords_file:
        for i, f in enumerate(c.split(",")):
            # get overall min and max values for both
            # longitude (vmxx[0]) and latitude (vmxx[1])
            f = float(f)
            vmin[i] = min(vmin[i], f)
            vmax[i] = max(vmax[i], f)

    coords = []
    coords_file.seek(0) # rewind temp file
    i = 0
    for c in coords_file:
        # read again the file to put a limited
        # set of coordinates in a list
        if i == 0:
            coords.append([float(n) for n in c.split(",")])
            i = int(count / circles_amount)
        i -= 1


#!/usr/bin/env python3
import zipfile
import tempfile
import re
import mmap
import os
import math
import argparse

def zgrep(filename, regex):
    """Yields every match of regex in a zip file like zgrep -o"""
    with tempfile.TemporaryDirectory() as tempdir:
        zf = zipfile.ZipFile(filename)
        path = zf.extract(zf.filelist[0], tempdir)
        with open(path, 'r+') as f:
            data = mmap.mmap(f.fileno(), 0)
            for match in re.finditer(regex, data):
                yield match.group().decode("utf8")

class TwoPointsEquation:
    """Class to find a linear equation from two points"""
    def __init__(self, x1, x2, y1, y2):
        self.slope = (y2 - y1) / (x2 - x1)
        self.interception = y1 - (x1 * self.slope)

    def calc(self, x):
        """Calculate the y for the given x"""
        return x * self.slope + self.interception

class Parser:
    """Get informations from the gps coordinates in a kmz file"""
    def __init__(self, filename, projection_function, max_coords):
        self.kmz = filename
        self.p_fun = projection_function
        self.max_coords = max_coords

    def __enter__(self):
        """Read the input file, find all coordinates,
        apply projection, calculate amount (self.count) and
        min/max values (self.ends) and store the projected
        coordinates in self.coords_file"""
        
        self.coords_file = tempfile.NamedTemporaryFile(
            mode='w+',
            encoding='utf-8',
            delete=False
        )

        self.count = 0
        
        self.ends = {
            'lng': [float('inf'), float('-inf')],
            'lat': [float('inf'), float('-inf')]
        }
        
        for c in zgrep(self.kmz, b"-?[0-9]+.[0-9]+,-?[0-9]+.[0-9]+"):
            
            coord = [float(n) for n in c.split(',')]
            coord[1] = self.p_fun(coord[1]) # project latitude

            for lxx, n in zip(('lng', 'lat'), coord):
                # get overall mininum and maximum values
                # for both longitude and latitude
                for i, f in enumerate((min, max)):
                    self.ends[lxx][i] = f(self.ends[lxx][i], n)
                    
            # store the projected coordinates
            print(','.join(map(str,coord)), file=self.coords_file)
            
            # get the count of how many coordinates we have
            self.count += 1
        
        return self

    def get_coords(self):
        """Yield the specimen of projcted coordinates"""
        self.coords_file.seek(0) # rewind temp file
        i = 0
        for c in self.coords_file:
            # read again the file yielding a limited
            # set of coordinates, roughly <= self.max_coords,
            # as a list of floats
            if i == 0:
                yield [float(n) for n in c.split(",")]
                i = int(self.count / self.max_coords)
            i -= 1

    def __exit__(self, *args):
        self.coords_file.close()
        os.unlink(self.coords_file.name)

class Resizer:
    """Class to rescale coordinates from a set of ends to another"""
    def __init__(self, origin_ends, target_ends):
        self.eq = {
            lxx: TwoPointsEquation(
                *origin_ends[lxx],
                *target_ends[lxx]
            )
            for lxx in ('lng', 'lat')
        }

    def resize(self, coord):
        lng, lat = coord
        return [
            self.eq['lng'].calc(lng),
            self.eq['lat'].calc(lat)
        ]

class SvgBuilder:
    """A simple svg image creator"""
    def __init__(self, filename, width, height, circle_radius):
        self.r = circle_radius
        self.outfile = open(filename, "w")
        print('<svg width="{}" height="{}">'.format(
            width, height), file=self.outfile)

    def __enter__(self):
        return self

    def circle(self, cx, cy):
        """Insert a circle at the given position"""
        print('<circle cx="{}" cy="{}" r="3"/>'.format(
            cx, cy), file=self.outfile)

    def __exit__(self, *args):
        print('</svg>', file=self.outfile)
        self.outfile.close()

def apply_ratio(o_w, o_h, t_w, t_h):
    """Calculate width or height to keep aspect ratio.

    o_w, o_h -- origin width and height
    t_w, t_h -- target width or height, the dimension
                to be calculated must be set to 0.
    
    Returns: (w, h) -- the new dimensions
    """
    new_w = t_h * o_w / o_h
    new_h = t_w * o_h / o_w
    return new_w+t_w, new_h+t_h

def ends_length(ends):
    """Reduce a dict of gps endings to their length"""
    return [ends[lxx][1]-ends[lxx][0] for lxx in ('lng', 'lat')]

def pad(t, padding):
    """Sum every non-zero item of t with padding*2"""
    return [0 if n==0 else n+padding*2 for n in t]

def diagnose(eqs, projection_f):
    """Print the math to turn a gps coordinate in a svg coordinate"""
    args = lambda lxx: (
        lxx,
        eqs[lxx].slope,
        eqs[lxx].interception
    )
    print("f = {}".format(projection_f))
    print("x = {} * {} + {}".format(*args('lng')))
    print("y = f({}) * {} + {}".format(*args('lat')))

project = 'lambda lat: 180/math.pi * math.log(math.tan(math.pi/4 + lat*(math.pi/180)/2))'
# Projection function as string

if __name__ == '__main__':

    argparser = argparse.ArgumentParser()
    argparser.add_argument('infile')
    argparser.add_argument(
        '--width', default=0, type=float
    )
    argparser.add_argument(
        '--height', default=0, type=float
    )
    argparser.add_argument(
        '--outfile', default='out.svg'
    )
    argparser.add_argument(
        '--padding', default=0, type=float
    )
    argparser.add_argument(
        '-circles-amount', default=1000, type=int
    )
    argparser.add_argument(
        '-circles-radius', default=3, type=float
    )
    args = argparser.parse_args()
    
    if args.width == args.height == 0:
        argparser.error('provide width or height or both')
        
    imgsize = [args.width, args.height]

    with Parser(args.infile, eval(project), args.circles_amount) as par:
        if not all(imgsize):
            imgsize = pad(
                apply_ratio(
                    *ends_length(par.ends),
                    *pad(imgsize, -args.padding)
                ), args.padding
            )
        with SvgBuilder(args.outfile, *imgsize, args.circles_radius) as svg:
            target_ends = {
                'lng': [args.padding, imgsize[0]-args.padding],
                'lat': [imgsize[1]-args.padding, args.padding]
            }
            res = Resizer(par.ends, target_ends)

            diagnose(res.eq, project)

            for c in par.get_coords():
                svg.circle(*res.resize(c))

#!/usr/bin/python3
"""
This file is responsible for OSM map image generation.
"""
import geotiler
import matplotlib.pyplot as plt
from source import log
import os

home_folder = os.path.expanduser('~')
try:
    os.makedirs(home_folder + '/.config/geotiler')
except FileExistsError:
    pass
with open(home_folder + '/.config/geotiler/geotiler.ini', 'w') as f:
    pass


def get_map(points, labels, image_size=(1024, 768)):
    '''
    points = [(49.8328013, 18.0440042), 
              (49.8309784, 18.1624547), 
              (49.8301379, 18.1641516),
              (49.7842545, 18.1237474),
              (49.9131799, 18.0989584), 
              #(49.5494967, 18.4044064),
              ] 
    labels = ['Home', 'VSB', 'Babylon', 'Klimkovice', 'Benesov']
    '''
    if not points:
        log.err('Cannot show map without point.')
        return None

    border_const = 0.005
    min_lat = min(p[0] for p in points) - border_const
    max_lat = max(p[0] for p in points) + border_const
    min_lon = min(p[1] for p in points) - border_const
    max_lon = max(p[1] for p in points) + border_const

    center = ((min_lon + max_lon) / 2, (min_lat + max_lat) / 2)
    """ count appropriate zoom """
    # https://wiki.openstreetmap.org/wiki/Zoom_levels
    if len(points) == 1:
        zoom = 18
    else:
        zoom = 0
        tmp_tile_width = 360
        while (tmp_tile_width > abs(max_lon - min_lon)
               and tmp_tile_width/2 > abs(max_lat - min_lat)):
            #print('Zoom', zoom, 'TTW', tmp_tile_width, 'latdiff', abs(max_lat - min_lat), 'londiff', abs(max_lon - min_lon))
            tmp_tile_width /= 2
            zoom += 1
        zoom = min(18, max(1, zoom + 1))
        #print('Center:', center)
        #print('Zoom:', zoom)

    fig = plt.figure(figsize=(20, 15), frameon=False)
    ax = plt.subplot(111)
    mm = geotiler.Map(center=center, size=image_size,
                      zoom=zoom, provider='osm')
    img = geotiler.render_map(mm)
    geo_points = [mm.rev_geocode(p[::-1]) for p in points]
    X, Y = zip(*geo_points)
    ax.axis('off')  # TODO remove border
    ax.imshow(img)
    ax.scatter(X, Y, marker='p', c='darkgreen',
               edgecolor='none', s=500, alpha=0.8)
    for x, y, label in zip(X, Y, labels):
        #ax.annotate(label, (x, y), (x+5, y-5))
        ax.text(x+5, y-5, label, fontsize=30)
        # TODO change positioning if overlap is expected
    return fig

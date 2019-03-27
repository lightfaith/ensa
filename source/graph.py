#!/usr/bin/python3
"""
This script generates graphs for relationship visualization.
"""
import os
import graphviz as gv
# import networkx as nx
# import matplotlib.pyplot as plt
# from collections import OrderedDict
import tempfile
from io import BytesIO


def get_relationship_color(relationship):
    colors = {
        'friend': 'lightblue',
        'sibling': 'orange',
        'spouse': 'purple',
        'parent': 'brown',
        'child': 'brown',
        'stepparent': 'chocolate',
        'stepchild': 'chocolate',
        'grandparent': 'brown4',
        'grandchild': 'brown4',
        'partner': 'magenta',
        'lover': 'maroon',
        'colleague': 'darkgreen',
        'lord': 'springgreen',
        'liege': 'springgreen',
        'enemy': 'red',
        'captive': 'firebrick2',
        'captor': 'firebrick2',
        'killer': 'firebrick4',
        'victim': 'firebrick4',
        'ally': 'turquoise',
        'foster': 'chocolate2',
        'guardian': 'chocolate2',
    }
    return colors.get(relationship) or 'black'


opposites = {
    'parent': 'child',
    'child': 'parent',
    'stepparent': 'stepchild',
    'stepchild': 'stepparent',
    'grandparent': 'grandchild',
    'grandchild': 'grandparent',
    'lord': 'liege',
    'liege': 'lord',
    'killer': 'victim',
    'victim': 'killer',
    'captor': 'captive',
    'captive': 'captor',
    'foster': 'guardian',
    'guardian': 'foster',
}


def get_relationship_graph(codename, acquaintances, relationships):
    """
    codename:      main codename we are interested in
    acquaintances: list of codename:str
    relationships: list of
                    ((codename:str, codename:str):
                     (relationship:str, level:int, accuracy:int, valid:bool))
    """
    path = os.path.join(tempfile.mkdtemp(), 'network')
    g = gv.Graph(filename=path, format='png',
                 engine='circo')
    g = gv.Graph(filename=path, format='png',
                 engine='sfdp')
    # g.node(codename)
    node_fontsize = '10'
    edge_fontsize = '8'
    g.node(codename, fontsize=node_fontsize, fontname='Helvetica')
    for node in acquaintances:
        g.node(node, fontsize=node_fontsize, fontname='Helvetica')
    for (a, b), (relationship, level, accuracy, valid) in relationships:
        """swap relationship if necessary"""
        if codename == a:
            relationship = opposites.get(relationship) or relationship
        g.edge(a,
               b,
               label=relationship + ' ' * 10,
               color=get_relationship_color(relationship),
               alpha='0.8',
               penwidth=str((level or 1) * (accuracy or 1) / 20),
               fontsize=edge_fontsize,
               fontname='Helvetica',
               style='solid' if valid else 'dotted')
    # g.view()
    g.render()
    with open(path + '.png', 'rb') as f:
        network_str = BytesIO(f.read())
    return network_str


'''
get_relationship_graph('ted',
                       ['robin', 'barney'],
                       [
                           ('ted', 'barney'): ('friend', 8, 10, True),
                           ('robin', 'ted'): ('friend', 10, 10, True),
                           ('lily', 'marshall'): ('spouse', 9, 9, False)]
                      )
'''

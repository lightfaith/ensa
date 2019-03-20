#!/usr/bin/python3
"""
This script generates graphs for relationship visualization.
"""
import os
import graphviz as gv
#import networkx as nx
#import matplotlib.pyplot as plt
#from collections import OrderedDict
import tempfile
from io import BytesIO


def get_relationship_color(relationship):
    colors = {
        'friend': 'lightblue',
        'sibling': 'orange',
        'spouse': 'purple',
        'parent': 'red',
        'child': 'red',
        'grandparent': 'brown',
        'grandchild': 'brown',
        'partner': 'pink',
        'colleague': 'green',
        '': '',
    }
    return colors.get(relationship) or 'black'
    if relationship == 'friend':
        return 'blue'
    elif relationship == 'spouse':
        return 'purple'
    else:
        return 'black'


def get_relationship_graph(codename, acquaintances, relationships):
    """
    codename:      main codename we are interested in
    acquaintances: list of codename:str
    relationships: list of 
                    ((codename:str, codename:str): 
                     (relationship:str, level:int, accuracy:int, valid:bool))
    """
    path = os.path.join(tempfile.mkdtemp(), 'network')
    g = gv.Graph(filename=path, format='png')
    # g.node(codename)
    node_fontsize = '10'
    edge_fontsize = '8'
    g.node(codename, fontsize=node_fontsize)
    for node in acquaintances:
        g.node(node, fontsize=node_fontsize)
    for (a, b), (relationship, level, accuracy, valid) in relationships:
        g.edge(a,
               b,
               label=relationship + ' ' * 10,
               color=get_relationship_color(relationship),
               penwidth=str((level or 1) * accuracy / 20),
               fontsize=edge_fontsize,
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

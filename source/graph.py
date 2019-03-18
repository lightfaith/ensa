#!/usr/bin/python3
"""
This script generates graphs for relationship visualization.
"""
import networkx as nx
import matplotlib.pyplot as plt
from collections import OrderedDict

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
    codename: main codename we are interested in
    acquaintances: list of codename:str
    relationships: dict of (codename:str, codename:str): 
                           (relationship:str, level:int, accuracy:int)
    """
    g = nx.Graph()
    g.add_node(codename, color='red')
    g.add_nodes_from(acquaintances)
    # TODO limit transitive relationships
    
    edges = OrderedDict([(k, v[0]) for k,v in relationships.items()])
    edge_colors = [get_relationship_color(v[0]) for _,v in relationships.items()]
    edge_weights = [v[1]*v[2]/20 for _,v in relationships.items()]
    g.add_edges_from(edges)
    
    fig = plt.figure(figsize=(20, 15), frameon=False)
    plt.subplot(111)
    pos = nx.shell_layout(g)
    #nx.draw_networkx_nodes(g, pos, node_size=10000, node_color='blue', alpha=0.3)
    nx.draw_networkx_nodes(g, pos, node_size=10000, node_color='blue', alpha=0)
    nx.draw_networkx_labels(g, pos, font_size=30, font_family='sans-serif')
    nx.draw_networkx_edges(g, pos, edge_color=edge_colors, width=edge_weights)
    nx.draw_networkx_edge_labels(g, pos, font_size=20, edge_labels=edges)
    plt.axis('off')
    #plt.show()
    return fig
'''
get_relationship_graph('ted', 
                       ['lily', 'marshall'], 
                       {
                           ('ted', 'lily'): ('friend', 8, 10), 
                           ('ted', 'marshall'): ('friend', 5, 2), 
                           ('lily', 'marshall'): ('spouse', 9, 9)}
                      )
'''

#!/usr/bin/python3
"""
This script generates graphs for relationship visualization.
"""
import os
import graphviz as gv
import networkx as nx
import matplotlib.pyplot as plt
from collections import OrderedDict
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
    g = nx.MultiGraph()
    g.add_node(codename, color='red')
    g.add_nodes_from(acquaintances)
    # TODO limit transitive relationships
    # TODO multigraph
    
    #edges = OrderedDict([(k, v[0]) for k,v in relationships])
    edges = [(*k, i) for i,(k,v) in enumerate(relationships)]
    edge_colors = [get_relationship_color(v[0]) 
                   for _,v in relationships]
    edge_weights = [v[1]*v[2]/20 
                    for _,v in relationships]
    edge_styles = [('solid' if v[3] else 'dotted') 
                   for _,v in relationships]
    '''
    #print(edges)
    #g.add_edges_from(edges)
    for edge, color, weight, style in zip(edges, edge_colors, edge_weights, edge_styles):
        g.add_edge(edge[0], edge[1], key=edge[2], relationship=relationships[edge[2]], color=color, weight=weight, style=style)
    print(g.edges) 
    fig = plt.figure(figsize=(20, 15), frameon=False)
    plt.subplot(111)
    pos = nx.shell_layout(g)
    #nx.draw_networkx_nodes(g, pos, node_size=10000, node_color='blue', alpha=0.3)
    nx.draw_networkx_nodes(g, pos, node_size=10000, node_color='blue', alpha=0)
    nx.draw_networkx_labels(g, pos, font_size=30, font_family='sans-serif')
    print(edge_colors)
    #nx.draw_networkx_edges(g, pos)
    nx.draw_networkx_edges(g, pos)
    #nx.draw_networkx_edges(g, pos, edge_color=edge_colors, width=edge_weights, style=edge_styles)
    edge_labels = nx.get_edge_attributes(g, 'relationship')
    nx.draw_networkx_edge_labels(g, pos, font_size=20, edge_labels=edge_labels)
    plt.axis('off')
    #plt.show()
    return fig
    '''
    path = os.path.join(tempfile.mkdtemp(), 'network')
    g = gv.Graph(filename=path, format='png')
    #g.node(codename)
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
               penwidth=str(level*accuracy/20),
               fontsize=edge_fontsize,
               style='solid' if valid else 'dotted')
    #g.view()
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

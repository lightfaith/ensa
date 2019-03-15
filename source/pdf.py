#!/usr/bin/python3
"""
This module is responsible for generating PDF reports of provided data.
"""
import os
import tempfile
import traceback

from reportlab.lib import colors, utils
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from source import ensa
from source.db import Database
from source.map import *

styles = getSampleStyleSheet()

def get_level_sort(infos):
    """
    Returns a list of (level, info) tuples sorted by level. Info in the
    tuple is actually list of corresponding info entries sorted 
    alphabetically by value.
    """
    infos_levels = {}
    for info in infos:
        if info[5] not in infos_levels:
            infos_levels[info[5]] = []
        infos_levels[info[5]].append(info)
    infos_levels = {k:sorted(v, key=lambda x:x[10]) 
                    for k,v in infos_levels.items()}
    return sorted(infos_levels.items(), key=lambda x: x[0] or 0, reverse=True)

get_valid = lambda infos,key: [i for i in infos if i[7] == 1 and i[4] == key]
par = lambda x: Paragraph(x, styles['BodyText'])

religion_symbols = {
    'atheist': '',
    'atheism': '',
    'christian': '\u271e',
    'christianity': '\u271e',
    'catholic': '\u271e',
    'jew': '\u2721',
    'judaism': '\u2721',
    'jewish': '\u2721',
    'muslim': '\u262a',
    'islam': '\u262a',
    'islamic': '\u262a',
    'buddhist': '\u262f',
    'buddhism': '\u262f',
    'shinto': '\u26e9',
    'shintoism': '\u26e9',
    'shintoist': '\u26e9',
    'hindu': '\U0001f549',
    'hinduist': '\U0001f549',
    'hinduism': '\U0001f549',
    'satanist': '\u26e7',
    'satanism': '\u26e7',
}
horoscope_symbols = {
    'aries': '\u2648',
    'taurus': '\u2649',
    'gemini': '\u264a',
    'cancer': '\u264b',
    'leo': '\u264c',
    'virgo': '\u264d',
    'libra': '\u264e',
    'scorpius': '\u264f',
    'sagittarius': '\u2650',
    'capricorn': '\u2651',
    'aquarius': '\u2652',
    'pisces': '\u2653',
}
politics_symbols = {
    'communist': '\u262d',
    'communism': '\u262d',
    #'nazi': '\u0fd5',
    #'nazism': '\u0fd5',
    #'nazist': '\u0fd5',
}


def get_valid_by_level(infos, key):
    """
    Returns only valid infos as get_valid method, but sorted by level.
    """
    return sorted(get_valid(infos, key), key=lambda x: x[5] or 0, reverse=True)

def get_valid_by_ids(infos, ids):
    return [i for i in infos if i[7] == 1 and i[0] in ids]

def get_valid_by_keyword(infos, keyword):
    return [i for i in infos if i[7] == 1 and keyword in i[11]]

test_colors = [colors.salmon, colors.yellow, colors.magenta, colors.lightgreen]
test_style = lambda x: TableStyle([
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('BACKGROUND', (0, 0), (-1, -1), test_colors[x]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
])


def person_report(infos, filename): # TODO give keywords, composites, etc. as argument
    #for info in infos:
    #    print(info)

    doc = SimpleDocTemplate(filename, pagesize=A4)
    font_file = 'source/symbola.ttf'
    symbola_font = TTFont('Symbola', font_file)
    styles['BodyText'].fontName = 'Symbola'
    styles['BodyText'].fontSize = 12
    pdfmetrics.registerFont(symbola_font)
    
    entries = []

    infos_dict = {info[4]:info for info in infos}
    """TITLE"""
    entries.append(Paragraph(
        '<para align=center spaceAfter=20>Person Report</para>',
        styles['Title']))
    
    """basic info"""
    name = ' '.join([i[10] for i in get_valid(infos, 'firstname')]
                    + [i[10] for i in get_valid(infos, 'middlename')]
                    + [i[10] for i in get_valid(infos, 'lastname')])
    try:
        sex = get_valid(infos, 'sex')[0][10]
        sex_symbol = ('\u2642' if sex == 'male' else 
                      ('\u2640' if sex == 'female' else ''))
    except:
        sex_symbol = ''
    try:
        orientation = get_valid(infos, 'orientation')[0][10]
        if orientation == 'bisexual':
            orientation_symbol = '\u26a4'
        elif orientation == 'homosexual':
            orientation_symbol = ('\u26a3' if sex == 'male' else 
                          ('\u26a2' if sex == 'female' else ''))
        else:
            orientation_symbol = '' # TODO any for hetero? or we call it default?
    except:
        orientation_symbol = ''
    '''
    #racial_modifiers = '\U0001f3fb\U0001f3fc\U0001f3fd\U0001f3fe\U0001f3ff'
    # http://unicode.org/charts/nameslist/n_2600.html
    font_testing = ('\u2642\u2640\u26a4\u26a3\u26a2 \u2620\u26ad\u2694\u2695\u2625\u26ad\u26ae\u26af\u267f\u271d' 
                   #+ ''.join('%s\U0001f46e' % r for r in racial_modifiers)
                   + ''.join(set(religion_symbols.values()))
                   + ''.join(set(horoscope_symbols.values()))
                   + ''.join(set(politics_symbols.values())))
    entries.append(par(font_testing))
    entries.append(par(''))
    #'''
    try:
        religion = get_valid_by_level(infos, 'religion')[0][10]
    except:
        religion = ''
    
    try:
        politics = get_valid_by_level(infos, 'politics')[0][10]
    except:
        politics = ''
    
    codename = get_valid(infos, 'codename')[0][10]
    basic_info = {
        'Codename': codename,
        'Name': name,
        'Known as': list(par(i[10]) for i in get_valid(infos, 'nickname')),
        'Identifier': list(par(i[10]) for i in get_valid(infos, 'identifier')),
        'Age': '', # TODO
        'Characteristics': ' '.join((sex_symbol, 
                                     orientation_symbol,
                                     religion_symbols.get(religion) or religion,
                                     politics_symbols.get(politics) or politics)
                                   ).strip(),
        'Phone': list(par(i[10]) for i in get_valid(infos, 'phone')),
        'Email': list(par(i[10]) for i in get_valid(infos, 'email')),
        'Website': list(par('<link href="%s">%s</link>' % (i[10], i[10])) 
                        for i in get_valid(infos, 'website')),
        #'Address': [par(line) for line in address],
    }
    # TODO rc, ico apod.
    """portrait"""
    '''
    try:
        portrait_id = get_valid(infos, 'portrait')[0][0]
    except:
        print('No portrait available.')
    '''
    portrait_path = 'files/binary/%d' % get_valid(infos, 'codename')[0][0]
    if os.path.isfile(portrait_path):
        portrait = Image(portrait_path)
    else:
        print('No portrait available.')
        import PIL.Image
        from io import BytesIO
        white = PIL.Image.new('RGB', (150, 200), (255, 255, 255))
        portrait_str = BytesIO()
        white.save(portrait_str, format='PNG')
        portrait = Image(portrait_str)
    portrait._restrictSize(7*cm, 10*cm)
    
    """Add basic info and portrait to the report"""
    entries.append(Table(
        [[Table(
              [[Paragraph('Basic information', styles['Heading2'])],
               [Table(
                   [[par(k), 
                    par(v) if type(v) == str else v] 
                    for k,v in basic_info.items() if v], 
                   colWidths=[3.5*cm, 9*cm], 
                   style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),])
                   #style=test_style(2),
                   )]], 
                #style=test_style(1), 
            hAlign='LEFT'), 
          portrait]], 
        colWidths=[10*cm, 7.5*cm],
        style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                          #('BACKGROUND', (0, 0), (-1, -1), test_colors[0]),
                          ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                         ]),
        hAlign='CENTER', 
        vAlign='TOP'))

    """Address"""
    description = '%s\'s home' % codename.title()
    """find address that is not part of a composite (e.g. work address)"""
    composites = [i for i in infos if i[3] == Database.INFORMATION_COMPOSITE]
    try:
        address = [a for a in infos 
                   if a[0] not in [x for i in composites for x in i[10]]
                   and a[3] == Database.INFORMATION_COMPOSITE
                   and a[4] == 'address']
        address_entries = {i[4]:i[10] 
                           for i in get_valid_by_ids(infos, address[0][10])}
        address_id = address[0][0]
        '''
        address = ['%s %s' % (address_entries.get('street') or '', 
                              address_entries.get('street_number') or ''), # TODO or reverse
                   '%s, %s %s' % (address_entries.get('city') or '',
                                  address_entries.get('province') or '',
                                  address_entries.get('postal') or ''),
                   address_entries.get('country') or '']
        '''
        address = [address_entries.get(x) or '' 
                   for x in ('street', 'street_number', 'city', 'province', 
                             'postal', 'country')]
    except:
        traceback.print_exc()
        address = ['']
    """get map"""
    # get associations with address
    address_map = None
    address_assocs = [a for a in ensa.db.get_associations_by_information(address_id)
                     if a[0][6] == description]
    # find association with location entry
    for address_assoc in address_assocs:
        if address_assoc[3]:
            address_locations = [x for x in address_assoc[3] 
                                if x[2] is not None and x[3] is not None]
            if address_locations:
                # create map, load as image
                with tempfile.NamedTemporaryFile() as f:
                    address_map = get_map([address_locations[0][2:4]], 
                                          [description])
                    address_map.savefig(
                        f.name + '.png', bbox_inches='tight', pad_inches=0)
                    address_map = Image(f.name + '.png')
                    address_map._restrictSize(12*cm, 12*cm)
    entries.append(Table([[[Paragraph('Address', styles['Heading2'])]
                           + [par(line) for line in address], 
                           address_map]], 
                         style=TableStyle([
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'), 
                         ]),
                         colWidths=[5.5*cm, 12*cm],
                         ))
    """Family"""
    entries.append(Paragraph('Family', styles['Heading2']))

    """Job"""
    entries.append(Paragraph('Job', styles['Heading2']))

    """Friends"""
    entries.append(Paragraph('Friends', styles['Heading2']))
    """Social bubble scheme"""

    """Credentials"""
    entries.append(Paragraph('Credentials', styles['Heading2']))

    """Likes, skills etc."""
    for category, category_name in (
            ('skill', 'Skills'), 
            ('likes', 'Likes'), 
            ('dislikes', 'Dislikes'), 
            ('trait', 'Traits'), 
            ('asset', 'Assets'), 
        ):
        valids = get_valid(infos, category)
        if valids:
            valids_levels = [(k, [x[10] for x in v]) 
                             for k,v in get_level_sort(valids)]
            t = Table([[par(str(level or '')), 
                        par('' + ', '.join(set(valids)))] 
                       for level, valids in valids_levels],
                      colWidths=[cm, 16*cm],
                      style=test_style(3))
            entries.append(KeepTogether([
                Paragraph(category_name, styles['Heading2']),
                t]))

    """ Timeline """
    entries.append(Paragraph('Timeline', styles['Heading2']))
    # TODO with description, shown images, map etc.
    
    """ medical """ # TODO ?

    """ gallery """
    images = get_valid_by_keyword(infos, 'image')
    if images:
        entries.append(Paragraph('Gallery', styles['Heading2']))
        images_dict = {}
        for image in images:
            key = '%s:%s' % (image[4], image[10])
            if key not in images_dict.keys():
                images_dict[key] = []
            images_dict[key].append(image)
        for key, imgs in sorted(images_dict.items(), key=lambda x: x[0]):
            heading = Paragraph(key, styles['Heading3'])
            imgs_in_category = []
            for img in imgs:
                try:
                    image = Image('files/binary/%d' % img[0])
                    image._restrictSize(3.5*cm, 5*cm)
                    #entries.append(image)
                    imgs_in_category.append(image)
                except:
                    traceback.print_exc()
                    continue
            columns = 4
            t = (Table([imgs_in_category[i:i+columns] 
                        for i in range(0, len(imgs_in_category), columns)],
                       hAlign='LEFT',
                       style=TableStyle([
                           #('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                       ])))
            entries.append(KeepTogether([heading, t]))
    """ build PDF from individual entries"""
    doc.build(entries)

#####
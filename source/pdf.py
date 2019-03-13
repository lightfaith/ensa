#!/usr/bin/python3
"""
This module is responsible for generating PDF reports of provided data.
"""
import traceback
from reportlab.lib import colors, utils
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


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

def get_valid_by_level(infos, key):
    """
    Returns only valid infos as get_valid method, but sorted by level.
    """
    return sorted(get_valid(infos, key), key=lambda x: x[5] or 0, reverse=True)



def person_report(infos, filename): # TODO give keywords, composites, etc. as argument
    #for info in infos:
    #    print(info)
    doc = SimpleDocTemplate(filename, pagesize=A4)
    font_file = 'source/symbola.ttf'
    symbola_font = TTFont('Symbola', font_file)
    styles['BodyText'].fontName = 'Symbola'
    styles['BodyText'].fontSize = 12
    pdfmetrics.registerFont(symbola_font)
    test_colors = [colors.salmon, colors.yellow, colors.magenta, colors.lightgreen]
    test_style = lambda x: TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BACKGROUND', (0, 0), (-1, -1), test_colors[x]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ])
    
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
    '''
    try:
        religion = get_valid_by_level(infos, 'religion')[0][10]
    except:
        traceback.print_exc()
        religion = ''
    try:
        politics = get_valid_by_level(infos, 'politics')[0][10]
    except:
        traceback.print_exc()
        politics = ''
    basic_info = {
        'Codename': get_valid(infos, 'codename')[0][10],
        'Name': name,
        'Known as': ', '.join(i[10] for i in get_valid(infos, 'nickname')),
        'Characteristics': ' '.join((sex_symbol, 
                                     orientation_symbol,
                                     religion_symbols.get(religion) or religion,
                                     politics_symbols.get(politics) or politics)),
        'Phone': list(par(i[10]) for i in get_valid(infos, 'phone')),
        'Email': list(par(i[10]) for i in get_valid(infos, 'email')),
    }
    # TODO address
    # TODO email, phone, ...
    # TODO rc, ico apod.
    """portrait"""
    try:
        portrait_id = get_valid(infos, 'portrait')[0][0]
    except:
        print('No portrait available.')
    portrait = Image('files/binary/%d' % portrait_id)
    portrait._restrictSize(7*cm, 10*cm)
    
    """Add basic info and portrait to the report"""
    entries.append(Table(
        [[Table(
              [[Paragraph('Basic information', styles['Heading2'])],
               [Table(
                   [[par(k), 
                    par(v) if type(v) == str else v] 
                    for k,v in basic_info.items()], 
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
    """Family"""
    """Job"""
    """Friends"""
    """Social bubble scheme"""
    """Credentials"""
    """Likes, skills etc."""
    # TODO filter binary 
    for category, category_name in (
            ('skill', 'Skills'), 
            ('likes', 'Likes'), 
            ('dislikes', 'Dislikes'), 
            ('trait', 'Traits'), 
            ('asset', 'Assets'), 
        ):
        valids = get_valid(infos, category)
        if valids:
            entries.append(Paragraph(category_name, styles['Heading2']))
            valids_levels = [(k, [x[10] for x in v]) 
                             for k,v in get_level_sort(valids)]
            t = Table([[par(str(level or '')), 
                        par('' + ', '.join(valids))] 
                       for level, valids in valids_levels],
                      colWidths=[cm, 16*cm],
                      style=test_style(3))
            entries.append(t)
    """ timeline """
    # TODO with description, shown images, map etc.
    """ gallery """
    # TODO get from 'image' keyword
    """ build PDF from individual entries"""
    doc.build(entries)

#####

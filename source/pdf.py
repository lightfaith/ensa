#!/usr/bin/python3
"""
This module is responsible for generating PDF reports of provided data.
"""
from datetime import datetime
import os
import tempfile
from dateutil.relativedelta import relativedelta
import traceback

from collections import OrderedDict
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
from source.graph import *

styles = getSampleStyleSheet()


def get_level_sort(infos):
    """
    Returns a list of (level, info) tuples sorted by level. Info in the
    tuple is actually list of corresponding info entries sorted
    alphabetically by value.
    """
    infos_levels = {}
    """create level: info list"""
    for info in infos:
        key = info[5] or ''
        if key not in infos_levels:
            infos_levels[key] = []
        infos_levels[key].append(info)

    """add infos with the similar level (0, '', None) together"""
    result = {}
    for k, v in infos_levels.items():
        if k not in result.keys():
            result[k] = []
        result[k] += v

    """sort the infos in each level"""
    for k, v in result.items():
        result[k] = sorted(v, key=lambda x: x[10])
    """sort levels"""
    return sorted(result.items(), key=lambda x: x[0] or 0, reverse=True)


def get_valid(infos, key): return [
    i for i in infos if i[7] == 1 and i[4] == key]


def par(x): return Paragraph(x, styles['BodyText'])


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
    # 'nazi': '\u0fd5',
    # 'nazism': '\u0fd5',
    # 'nazist': '\u0fd5',
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


def test_style(x): return TableStyle([
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('BACKGROUND', (0, 0), (-1, -1), test_colors[x]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
])


def person_report(infos, filename):  # TODO give keywords, composites, etc. as argument
    # for info in infos:
    #    print(info)

    doc = SimpleDocTemplate(filename, pagesize=A4)
    font_file = 'source/symbola.ttf'
    symbola_font = TTFont('Symbola', font_file)
    styles['BodyText'].fontName = 'Symbola'
    styles['BodyText'].fontSize = 12
    pdfmetrics.registerFont(symbola_font)

    entries = []

    infos_dict = {info[4]: info for info in infos}
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
            orientation_symbol = ''  # TODO any for hetero? or we call it default?
    except:
        orientation_symbol = ''
    '''
    # racial_modifiers = '\U0001f3fb\U0001f3fc\U0001f3fd\U0001f3fe\U0001f3ff'
    # http://unicode.org/charts/nameslist/n_2600.html
    font_testing = ('\u2642\u2640\u26a4\u26a3\u26a2 \u2620\u26ad\u2694\u2695\u2625\u26ad\u26ae\u26af\u267f\u271d'
                   # + ''.join('%s\U0001f46e' % r for r in racial_modifiers)
                   + ''.join(set(religion_symbols.values()))
                   + ''.join(set(horoscope_symbols.values()))
                   + ''.join(set(politics_symbols.values())))
    entries.append(par(font_testing))
    entries.append(par(''))
    # '''
    try:
        religion = get_valid_by_level(infos, 'religion')[0][10]
    except:
        religion = ''

    try:
        politics = get_valid_by_level(infos, 'politics')[0][10]
    except:
        politics = ''

    codename_tuple = get_valid(infos, 'codename')[0]
    codename_id = codename_tuple[0]
    codename = codename_tuple[10]

    """Birth, death"""
    #import pdb
    # pdb.set_trace()
    time_events = {}
    for event in ['birth', 'death']:
        event_str = ''
        event_value = None
        description = '%s\'s %s' % (codename.title(), event)
        time_assocs = [a for a in ensa.db.get_associations_by_subject(codename)
                       if a[0][6] == description]
        # find association with time entry
        for time_assoc in time_assocs:
            # time entry present and valid?
            if time_assoc[2] and time_assoc[2][0][3]:
                event_str = time_assoc[2][0][1].partition(' ')[0]
                event_value = datetime.strptime(event_str, '%Y-%m-%d')
                event_str = datetime.strftime(event_value, '%-d. %-m. %Y')
                break
        # get partial info from Information
        if not event_value:
            try:
                year = get_valid(infos, '%s_year' % event)[0][10]
            except:
                year = None
            try:
                month = get_valid(infos, '%s_month' % event)[0][10]
            except:
                month = '1'
            try:
                day = get_valid(infos, '%s_day' % event)[0][10]
            except:
                day = '0'
            if year:  # at least
                event_str = '-'.join(filter(None, [year, month, day]))
                try:
                    event_value = datetime.strptime(event_str, '%Y-%m-%d')
                except:
                    pass

        if event_str:
            time_events[event] = (event_str, event_value)

    # compute age if birth, add to birth or death
    if 'birth' in time_events.keys():
        if 'death' in time_events.keys():
            age = relativedelta(
                time_events['death'][1], time_events['birth'][1]).years
            time_events['death'] = '%s (age %s)' % (
                time_events['death'][0], age)
        else:
            age = relativedelta(datetime.now(), time_events['birth'][1]).years
            time_events['birth'] = '%s (age %s)' % (
                time_events['birth'][0], age)
    # just keep the string version
    for k, v in time_events.items():
        if type(v) == tuple:
            time_events[k] = v[0]

    """ compose basic info """
    basic_info = OrderedDict([
        ('Codename', codename),
        ('Name', name),
        ('Identifier', list(par(i[10])
                            for i in get_valid(infos, 'identifier'))),
        ('Birth', time_events.get('birth')),
        ('Death', time_events.get('death')),
        # TODO age
        ('Known as', list(par(i[10]) for i in get_valid(infos, 'nickname'))),
        ('Characteristics', ' '.join((sex_symbol,
                                      orientation_symbol,
                                      religion_symbols.get(
                                          religion) or religion,
                                      politics_symbols.get(politics) or politics)
                                     ).strip()),
        ('Phone', list(par(i[10]) for i in get_valid(infos, 'phone'))),
        ('Email', list(par(i[10]) for i in get_valid(infos, 'email'))),
        ('Website', list(par('<link href="%s">%s</link>' % (i[10], i[10]))
                         for i in get_valid(infos, 'website'))),
    ])
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
                  for k, v in basic_info.items() if v],
                 colWidths=[3.5*cm, 9*cm],
                 style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ])
                 # style=test_style(2),
             )]],
            # style=test_style(1),
            hAlign='LEFT'),
          portrait]],
        colWidths=[10*cm, 7.5*cm],
        style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                          # ('BACKGROUND', (0, 0), (-1, -1), test_colors[0]),
                          # ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
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
        if address:
            address_entries = {i[4]: i[10]
                               for i in get_valid_by_ids(infos, address[0][10])}
            address_id = address[0][0]
            address = [address_entries.get(x) or ''
                       for x in ('street', 'street_number', 'city', 'province',
                                 'postal', 'country')]
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
    except:
        traceback.print_exc()
        address = ['']

    """Social Network"""
    relationships = [
        r for r in ensa.db.get_associations_by_information(codename_id)
        if len([info for info in r[1] if info[4] == 'codename']) == 2
        and (r[0][6].lower().startswith('%s-%s '
                                        % (r[1][0][10], r[1][1][10]))
             or r[0][6].lower().startswith('%s-%s '
                                           % (r[1][1][10], r[1][0][10]))
             )
    ]

    # prepare dict as (codename, codename): (relationship, level, accuracy)
    relationships = [((r[1][0][10],
                       r[1][1][10]),
                      (r[0][6].partition(' ')[2],
                       r[0][2],
                       r[0][3],
                       bool(r[0][4])))
                     for r in relationships]
    acquaintances = set(sum([k for k, _ in relationships], ()))
    acquaintances.remove(codename)
    # create network, load as image
    network = None
    '''
    with tempfile.NamedTemporaryFile() as f:
        network = get_relationship_graph(
            codename, acquaintances, relationships)
        network.savefig(
            f.name + '.png', bbox_inches='tight', pad_inches=0)
        network = Image(f.name + '.png')
    '''
    network_str = get_relationship_graph(
        codename, acquaintances, relationships)
    network = Image(network_str)
    network._restrictSize(17*cm, 30*cm)
    entries.append(KeepTogether([
        Paragraph('Social Network',
                  styles['Heading2']), network]))

    """Job"""
    entries.append(Paragraph('Job', styles['Heading2']))

    """Credentials"""
    entries.append(Paragraph('Credentials', styles['Heading2']))

    """Likes, skills etc."""
    for category, category_name in (
        ('skill', 'Skills'),
        ('likes', 'Likes'),
        ('dislikes', 'Dislikes'),
        ('trait', 'Traits'),
        ('asset', 'Assets'),
        ('medical', 'Medical conditions'),
    ):
        valids = get_valid(infos, category)
        if valids:
            valids_levels = [(k, [x[10] for x in v])
                             for k, v in get_level_sort(valids)]
            t = Table([[par(str(level or '')),
                        par('' + ', '.join(set(valids)))]
                       for level, valids in valids_levels],
                      colWidths=[cm, 15*cm],
                      style=test_style(3),
                      )
            entries.append(KeepTogether([
                Paragraph(category_name, styles['Heading2']),
                t]))

    """ Timeline """
    entries.append(Paragraph('Timeline', styles['Heading2']))
    # TODO with description, shown images, map etc.

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
                    # entries.append(image)
                    imgs_in_category.append(image)
                except:
                    traceback.print_exc()
                    continue
            columns = 4
            t = (Table([imgs_in_category[i:i+columns]
                        for i in range(0, len(imgs_in_category), columns)],
                       hAlign='LEFT',
                       style=TableStyle([
                           # ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                       ])))
            entries.append(KeepTogether([heading, t]))
    """ build PDF from individual entries"""
    doc.build(entries)

#####

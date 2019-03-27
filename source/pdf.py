#!/usr/bin/python3
"""
This module is responsible for generating PDF reports of provided data.
"""
from datetime import datetime
import os
import pdb
import tempfile
from dateutil.relativedelta import relativedelta
import traceback

from collections import OrderedDict
from reportlab.lib import colors, utils
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet  # , ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from itertools import zip_longest

from source import ensa
from source.db import Database
from source.map import *
from source.graph import *

styles = getSampleStyleSheet()


def par(x): return Paragraph(x,
                             styles['BodyText'])


def center_par(x): return Paragraph('<para align="center">%s</para>' % x,
                                    styles['BodyText'])


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


def get_valid(infos, key, codename_id=None):
    if codename_id:
        return [i for i in infos if i[1] == codename_id and i[7] == 1 and i[4] == key]
    else:
        return [i for i in infos if i[7] == 1 and i[4] == key]


def get_valid_by_level(infos, key, codename_id=None):
    """
    Returns only valid infos as get_valid method, but sorted by level.
    """
    return sorted(get_valid(infos, key, codename_id), key=lambda x: x[5] or 0, reverse=True)


def get_valid_by_ids(infos, ids, codename_id=None):
    if codename_id:
        return [i for i in infos if i[1] == codename_id and i[7] == 1 and i[0] in ids]
    else:
        return [i for i in infos if i[7] == 1 and i[0] in ids]


def get_valid_by_keyword(infos, keyword, codename_id=None):
    if codename_id:
        return [i for i in infos if i[1] == codename_id and i[7] == 1 and keyword in i[11]]
    else:
        return [i for i in infos if i[7] == 1 and keyword in i[11]]


def get_by_keyword(infos, keyword, codename_id=None):
    if codename_id:
        return [i for i in infos if i[1] == codename_id and keyword in i[11]]
    else:
        return [i for i in infos if keyword in i[11]]


def format_address(components):
    parts = {i[4]: i[10] for i in components}
    lines = [
        '%s %s' % (parts.get('street') or '',
                   parts.get('street_number') or ''),
        '%s %s' % ((parts.get('city') + ',') if 'city' in parts.keys() else '',
                   parts.get('province') or ''),
        '%s %s' % (parts.get('postal') or '', parts.get('country') or ''),
    ]
    return [line for line in lines if line.strip()]


test_colors = [colors.salmon, colors.yellow, colors.magenta, colors.lightgreen]


def test_style(x): return TableStyle([
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('BACKGROUND', (0, 0), (-1, -1), test_colors[x]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
])


religion_symbols = {
    'atheist': '\U0001f412',
    'atheism': '\U0001f412',
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
    # 'nazi': '\u0fd5', # not even \u5350
    # 'nazism': '\u0fd5',
    # 'nazist': '\u0fd5',
}

horoscope = [
    # sign, month, day<
    ('capricorn', 1, 20),
    ('aquarius', 2, 19),
    ('pisces', 3, 21),
    ('aries', 4, 20),
    ('taurus', 5, 21),
    ('gemini', 6, 21),
    ('cancer', 7, 23),
    ('leo', 8, 23),
    ('virgo', 9, 23),
    ('libra', 10, 23),
    ('scorpio', 11, 22),
    ('saggitarius', 12, 22),
]


# def person_report(infos, filename):
def person_report(codename, filename):
    codename_id = ensa.db.select_subject(codename)
    # pdb.set_trace()
    # info_codename_id = [x[0] for x in get_valid(
    #    infos, 'codename') if x[10] == codename][0]
    infos = ensa.db.get_informations(
        no_composite_parts=False, force_no_current_subject=True)
    # pdb.set_trace()
    infos = [i + ([x[1] for x in ensa.db.get_keywords_for_informations(i[0], force_no_current_subject=True)],)
             for i in infos]

    images = get_valid_by_keyword(infos, 'image')
    own_images = get_valid_by_keyword(infos, 'image', codename_id)
    print(own_images)
    composites = [i for i in infos if i[3] == Database.INFORMATION_COMPOSITE]
    own_composites = [i for i in infos if i[3] ==
                      Database.INFORMATION_COMPOSITE and i[1] == codename_id]

    # for info in infos:
    #    print(info)

    doc = SimpleDocTemplate(filename, pagesize=A4)
    font_file = 'source/symbola.ttf'
    symbola_font = TTFont('Symbola', font_file)
    styles['BodyText'].fontName = 'Symbola'
    styles['BodyText'].fontSize = 12
    pdfmetrics.registerFont(symbola_font)

    entries = []

    # infos_dict = {info[4]: info for info in infos}
    """TITLE"""
    entries.append(Paragraph(
        '<para align=center spaceAfter=20>Person Report</para>',
        styles['Title']))
    # TODO generation timestamp

    """basic info"""
    name = ' '.join([i[10] for i in get_valid(infos, 'firstname', codename_id)]
                    + [i[10]
                        for i in get_valid(infos, 'middlename', codename_id)]
                    + [i[10] for i in get_valid(infos, 'lastname', codename_id)])
    try:
        sex = get_valid(infos, 'sex', codename_id)[0][10]
        sex_symbol = ('\u2642' if sex == 'male' else
                      ('\u2640' if sex == 'female' else ''))
    except:
        sex_symbol = ''
    try:
        orientation = get_valid(infos, 'orientation', codename_id)[0][10]
        if orientation == 'heterosexual':
            orientation_symbol = '\u26a4'
        elif orientation == 'bisexual':
            orientation_symbol = '\u26a5'
        elif orientation == 'homosexual':
            orientation_symbol = ('\u26a3' if sex == 'male' else
                                  ('\u26a2' if sex == 'female' else ''))
        else:
            orientation_symbol = ''
    except:
        orientation_symbol = ''
    '''
    # racial_modifiers = '\U0001f3fb\U0001f3fc\U0001f3fd\U0001f3fe\U0001f3ff'
    # http://unicode.org/charts/nameslist/n_2600.html
    # http://xahlee.info/comp/unicode_plants_flowers.html
    font_testing = ('\u2642\u2640\u26a4\u26a5\u26a3\u26a2\u2620\u26ad\u2694\u2695\u2625\u26ad\u26ae\u26af\u267f\u271d'
                    # + ''.join('%s\U0001f46e' % r for r in racial_modifiers)
                    + '\u23f0\U0001f570\u231a\u23f1\u23f2\u231b\u23f3\u29d7\u29d6\U0001f550\U0001f5d3\U0001f4c5\U0001f4c6'  # clocks
                    + '\U0001f464\U0001f468'  # people
                    + '\U0001f30b\U0001fb5b\U0001f5fa\U0001f30d\U0001f30e\U0001f30f'  # locations
                    + '\U0001f4d1\U0001f4f0\U0001f4da\U0001f4dd\U0001f4dc\U0001f4c3\U0001f4c4'  # informations
                    + '\U0001f418\U0001f98f\U0001f42b\U0001f427\U0001f40b\U0001f420\U0001f42c\U0001f426\U0001f428\U0001f405\U0001f406\U0001f40e\U0001f981\U0001f98a\U0001f42f\U0001f412'  # animals
                    + '\U0001f4e6\U0001f4bc'  # items
                    + '\u26bf\U0001f5dd\U0001f511\U0001f50f\U0001f510\U0001f512\U0001f513'  # security
                    + '\U0001f3e2\U0001f3ed\U0001f3e0\U0001f3d8\U0001f3db'  # buildings
                    + ''.join(set(religion_symbols.values()))
                    + ''.join(set(horoscope_symbols.values()))
                    + ''.join(set(politics_symbols.values())))
    entries.append(par(font_testing))
    entries.append(par(''))
    # '''
    try:
        religion = get_valid_by_level(infos, 'religion', codename_id)[0][10]
    except:
        religion = ''

    try:
        politics = get_valid_by_level(infos, 'politics', codename_id)[0][10]
    except:
        politics = ''

    codename_tuple = get_valid(infos, 'codename', codename_id)[0]
    info_codename_id = codename_tuple[0]
    # codename = codename_tuple[10]

    """Birth, death"""
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
                year = get_valid(infos, '%s_year' % event, codename_id)[0][10]
            except:
                year = None
            try:
                month = get_valid(infos, '%s_month' %
                                  event, codename_id)[0][10]
                real_month = month
            except:
                month = '01'
                real_month = '??'
            try:
                day = get_valid(infos, '%s_day' % event, codename_id)[0][10]
                real_day = day
            except:
                day = '01'
                real_day = '??'
            if year:  # at least
                event_str = '-'.join(filter(None, [year, month, day]))
                try:
                    event_value = datetime.strptime(event_str, '%Y-%m-%d')
                except:
                    pass
                event_str = '-'.join(filter(None,
                                            [year, real_month, real_day]))

        if event_str:
            time_events[event] = (event_str, event_value)

    # compute age if birth, add to birth or death
    birth_sign = ''
    if 'birth' in time_events.keys():
        # and also get the zodiac sign
        if '?' not in time_events['birth'][0]:
            for i in range(len(horoscope)):
                sign, m, d_limit = horoscope[i]
                if time_events['birth'][1].month == m:
                    if time_events['birth'][1].day < d_limit:
                        birth_sign = horoscope_symbols[sign]
                    else:
                        birth_sign = horoscope_symbols[horoscope[(
                            i+1) % 12][0]]
                    break
        else:
            birth_sign = ''

        if 'death' in time_events.keys():
            age = relativedelta(
                time_events['death'][1], time_events['birth'][1]).years
            time_events['death'] = '%s (age %s)' % (
                time_events['death'][0], age)
            time_events['birth'] = '%s %s' % (
                time_events['birth'][0], birth_sign)
        else:
            age = relativedelta(datetime.now(), time_events['birth'][1]).years
            time_events['birth'] = '%s %s (age %s)' % (
                time_events['birth'][0], birth_sign, age)

    # just keep the string version
    for k, v in time_events.items():
        if type(v) == tuple:
            time_events[k] = v[0]

    """ compose basic info """
    basic_info = OrderedDict([
        ('Codename', codename),
        ('Name', name),
        ('Identifier', list(par(i[10])
                            for i in get_valid(infos, 'identifier', codename_id))),
        ('Birth', time_events.get('birth')),
        ('Death', time_events.get('death')),
        ('Known as', list(par(i[10])
                          for i in get_valid(infos, 'nickname', codename_id))),
        ('Characteristics', ' '.join((sex_symbol,
                                      orientation_symbol,
                                      religion_symbols.get(
                                          religion) or religion,
                                      politics_symbols.get(politics) or politics)
                                     ).strip()),
        ('Phone', list(par(i[10])
                       for i in get_valid(infos, 'phone', codename_id))),
        ('Email', list(par(i[10])
                       for i in get_valid(infos, 'email', codename_id))),
        ('Website', list(par('<link href="%s">%s</link>' % (i[10], i[10]))
                         for i in get_valid(infos, 'website', codename_id))),
    ])
    portrait_path = 'files/binary/%d' % info_codename_id
    if os.path.isfile(portrait_path):
        portrait = Image(portrait_path)
    else:
        log.warn('No portrait available.')
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
    try:
        address = [a for a in infos
                   if a[0] not in [x for i in own_composites for x in i[10]]
                   and a[3] == Database.INFORMATION_COMPOSITE
                   and a[4] == 'address']
        if address:
            address_id = address[0][0]
            address_lines = format_address(
                get_valid_by_ids(infos, address[0][10], codename_id))
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
                        # write lat&lon to address
                        lat, lon = address_locations[0][2:4]
                        lat_str = '%.6f\u00b0 %c' % (
                            abs(lat), 'N' if lat > 0 else 'S')
                        lon_str = '%.6f\u00b0 %c' % (
                            abs(lon), 'E' if lon > 0 else 'W')
                        address_lines.append('%s %s' % (lat_str, lon_str))
                        # create map, load as image
                        with tempfile.NamedTemporaryFile() as f:
                            address_map = get_map([(lat, lon)],
                                                  [description])
                            address_map.savefig(
                                f.name + '.png', bbox_inches='tight', pad_inches=0)
                            address_map = Image(f.name + '.png')
                            address_map._restrictSize(12*cm, 12*cm)
            if address_lines:
                entries.append(Table([[[Paragraph('Address', styles['Heading2'])]
                                       + [par(line) for line in address_lines],
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
    emblem_categories = [('person', '\U0001f464'),
                         ('organization', '\U0001f3ed'),
                         ('animal', '\U0001f418'),
                         ('item', '\U0001f4e6'),
                         ]
    # TODO add colleagues
    # pdb.set_trace()
    relationships = [
        # r for r in ensa.db.get_associations_by_information(info_codename_id)
        r for r in ensa.db.get_associations_by_subject(codename)
        if len([info for info in r[1] if info[4] in ('codename', 'position')]) == 2
        and (r[0][6].lower().startswith('%s-%s '
                                        % (ensa.db.get_subject_codename(r[1][0][1]), ensa.db.get_subject_codename(r[1][1][1])))
             or r[0][6].lower().startswith('%s-%s '
                                           % (ensa.db.get_subject_codename(r[1][1][1]), ensa.db.get_subject_codename(r[1][0][1])))
             )
    ]
    #print('relationships:', relationships)
    '''
    emblems = {}
    for r in relationships:
        print(r[0][6])
    '''
    # prepare dict as (codename, codename): (relationship, level, accuracy, validity)
    relationships = [((ensa.db.get_subject_codename(r[1][0][1]),
                       ensa.db.get_subject_codename(r[1][1][1])),
                      (r[0][6].partition(' ')[2],
                       r[0][2],
                       r[0][3],
                       bool(r[0][4])))
                     for r in relationships]

    # pick all colleagues, add relationships
    jobs = [a for a in ensa.db.get_associations_by_subject(
        codename) if a[0][6].endswith('employee')]
    companies = [info[0] for job in jobs for info in job[1]]
    colleagues = [i for a in ensa.db.get_associations_by_information(companies)
                  if a[0][6].endswith('employee') for i in a[1]]
    #print('companies:', companies)
    #print('col:', colleagues)
    '''
    job_infos = [i for i in infos if i[4] ==
                 'position' and i[1] == codename_id]
    colleagues = [i for a in ensa.db.get_associations_by_information(
        [i[0] for i in job_infos]) for i in a[1]]
    '''
    # get original infos with keywords etc.
    colleagues = [i for i in infos if i[0] in [c[0] for c in colleagues]]
    colleagues_used = []
    for colleague in colleagues:
        if colleague[1] == codename_id:
            continue
        if 'organization' in colleague[11]:
            continue
        colleague_codename = ensa.db.get_subject_codename(colleague[1])
        # TODO average with own?
        level = colleague[5]
        accuracy = colleague[6]
        valid = bool(colleague[7])
        if (colleague[1], valid) in colleagues_used:
            continue
        colleagues_used.append((colleague[1], valid))
        relationships.append(
            ((codename, colleague_codename), ('colleague', level, accuracy, valid)))

    # print(colleagues)
    acquaintances = set(sum([k for k, _ in relationships], ()))
    if acquaintances:
        '''
        """find emblems for each acquaintance"""
        emblems = {}
        for acq_info in [i for i in infos if i[4] == 'codename' and i[10] in acquaintances]:
            for category, emblem in emblem_categories:
                if category in acq_info[11]:
                    emblems[acq_info[10]] = emblem
                    break
        '''
        acquaintances.remove(codename)
        # create network, load as image
        network = None
        network_str = get_relationship_graph(
            codename, acquaintances, relationships)
        # codename, acquaintances, relationships, emblems)
        network = Image(network_str)
        network._restrictSize(17*cm, 30*cm)
        entries.append(KeepTogether([
            Paragraph('Social Network',
                      styles['Heading2']), network]))

    """Job"""
    organization_list = []  # for later map drawing
    # pdb.set_trace()
    jobs = [a for a in ensa.db.get_associations_by_subject(
        codename) if a[0][6].endswith('employee')]
    # TODO sort by start time desc
    job_tables = []
    # for j in jobs:
    #    print(j)
    for job in jobs:
        # pdb.set_trace()
        # skip invalid
        # if not job[0][4]:
        #    print('INVALID')
        #    continue
        job_id = job[0][0]
        try:
            start_date = [x[1].partition(' ')[0]
                          for x in job[2] if 'start date as employee' in x[5]][0]
        except:
            start_date = None
        try:
            end_date = [x[1].partition(
                ' ')[0] for x in job[2] if 'end date as employee' in x[5]][0]
        except:
            end_date = None

        # find the organization
        try:
            info_organization = [i for i in infos if i[0] in [
                i2[0] for i2 in job[1]] if 'organization' in i[11]][0]
            organization_list.append(info_organization[10])
            organization_id = ensa.db.select_subject(info_organization[10])
        except:
            traceback.print_exc()
            log.warn(
                'Found employee association without organization (#%d).' % job_id)
            continue

        information_row = []
        positions = [i for i in job[1] if i[1] ==
                     codename_id and i[4] == 'position']
        # print(positions, organization)
        # pdb.set_trace()
        try:
            organization_name = get_valid(infos, 'name', organization_id)[0]
            # organization_websites = get_valid(
            #    infos, 'website', organization_id)
            # organization_identifiers = get_valid(
            #    infos, 'identifier', organization_id)
            # organization_accounts = get_valid(
            #    infos, 'account', organization_id)
            # address, map - not here, just in organization report
        except:
            traceback.print_exc()
            continue

        try:
            logo_path = 'files/binary/%d' % organization_id
            logo = Image(logo_path)
            logo._restrictSize(3*cm, 2*cm)
        except:
            logo = None

        information_row.append(
            Paragraph(organization_name[10], styles['Heading3']))
        information_row.append(logo)
        # for identifier in organization_identifiers:
        #    information_row.append(par(identifier[10]))
        for position in positions:
            information_row.append(par(position[10]))
        # for website in organization_websites:
        #    information_row.append(website[10])
        # for account in organization_accounts:
        #    information_row.append(account[10])

        date_string = ('%s - %s' % (start_date or '?', end_date or '?')
                       if start_date or end_date else '')

        # add the complete job entry
        for position in positions:
            job_tables.append(
                Table([
                    [logo, Paragraph(organization_name[10],
                                     styles['Heading3'])],
                    ['', date_string],
                    ['', position[10]],
                ],
                    colWidths=[4*cm, 12*cm],
                    style=TableStyle([
                        ('SPAN', (0, 0), (0, -1)),
                        # ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                        # ('GRID', (0, 0), (-1, -1), 0.5, 'black'),
                    ])
                )
            )
    if job_tables:
        entries.append(KeepTogether([
            Paragraph('Job', styles['Heading2']),
            Table([[jt] for jt in job_tables],
                  colWidths=[16*cm],
                  style=TableStyle([
                      # ('GRID', (0, 0), (-1, -1), 0.5, 'gray'),
                      ('LINEBELOW', (0, 0), (-1, -1), 0.5, 'gray'),
                  ])
                  ),
        ]))

    """Credentials"""
    # get valid credentials for systems
    credentials = []
    credential_tuples = get_valid_by_keyword(infos, 'credentials', codename_id)
    for c in credential_tuples:
        system = c[4]
        creds = get_valid_by_ids(infos, c[10], codename_id)
        try:
            username = [c[10] for c in creds if c[4] == 'username'][0]
            password = [c[10] for c in creds if c[4] == 'password'][0]
        except:
            continue
        credentials.append((system, '%s:%s' % (username, password)))

    if credentials:
        entries.append(KeepTogether([
            Paragraph('Credentials', styles['Heading2']),
            Table(credentials,
                  colWidths=[4*cm, 12*cm],
                  style=TableStyle([
                      ('GRID', (0, 0), (-1, -1), 0.5, 'black'),
                  ])
                  )
        ]))
    # get all usernames, passwords (even invalid)
    usernames = [i[10]
                 for i in infos if i[1] == codename_id and i[4] == 'username']
    if usernames:
        entries.append(KeepTogether([
            Paragraph('Usernames', styles['Heading3']),
            Table([[u] for u in usernames], colWidths=[16*cm])]))

    passwords = [i[10]
                 for i in infos if i[1] == codename_id and i[4] == 'password']
    if passwords:
        entries.append(KeepTogether([
            Paragraph('Passwords', styles['Heading3']),
            Table([[u] for u in passwords], colWidths=[16*cm])]))

    # TODO suggest possible (by family etc.)

    """Likes, skills etc."""
    for category, category_name in (
        ('skill', 'Skills'),
        ('likes', 'Likes'),
        ('dislikes', 'Dislikes'),
        ('trait', 'Traits'),
        ('asset', 'Assets'),
        ('medical', 'Medical conditions'),
    ):
        valids = get_valid(infos, category, codename_id)
        if valids:
            valids_levels = [(k, [x[10] for x in v])
                             for k, v in get_level_sort(valids)]
            t = Table([[par(str(level or '')),
                        par('' + ', '.join(sorted(set(valids))))]
                       for level, valids in valids_levels],
                      colWidths=[cm, 15*cm],
                      # style=test_style(3),
                      )
            entries.append(KeepTogether([
                Paragraph(category_name, styles['Heading2']),
                t]))

    """ Quotations """
    valids = get_valid(infos, 'quotation', codename_id)
    if valids:
        entries.append(Paragraph('Quotations', styles['Heading2']))
        for valid in valids:
            entries.append(Paragraph('<i>%s</i>' %
                                     valid[10], getSampleStyleSheet()['BodyText']))

    """ Timeline """
    timeline = ensa.db.get_timeline_by_subject(codename)
    event_tables = []

    for event in timeline:
        # skip invalid
        if not event[0][4]:
            continue
        event_time = event[2][0][1]
        event_name = event[0][6]
        event_id = event[0][0]

        # first times if not the main time; \u23f0 or \U0001f4c6
        time_rows = []
        for time in event[2]:
            description = ('%s (%s)' %
                           (time[5], time[1])) if time[5] else ('%s' % time[1])
            if not time[3]:
                description = '<strike>%s</strike>' % description
            time_rows.append(
                par('\U0001f4c6 %s' % description))

        # then codenames (prefer with image); \U0001f464
        # then informations (prefer with image); \U001f4dd
        codename_rows = []
        information_rows = []
        for info in event[1]:
            # get info from infos (components, keywords, etc. present)...
            info = [i for i in infos if i[0] == info[0]][0]
            try:
                photo_path = 'files/binary/%d' % info[0]
                photo = Image(photo_path)
                photo._restrictSize(2*cm, 3*cm)
            except:
                photo = None
                # TODO codename image if not info image...
            if info[4] == 'codename':
                symbol = ''
                for category, emblem in emblem_categories:
                    if category in info[11]:
                        symbol = emblem
                        break
                rows = codename_rows
            else:
                symbol = '\U0001f4dd &lt;%s&gt; %s:' % (
                    ensa.db.get_subject_codename(info[1]), info[4])
                rows = information_rows
            #  get data if composite
            if info[3] == Database.INFORMATION_COMPOSITE:
                components = [(i[4], i[10])
                              for i in infos if i[0] in info[10]]
                text = '\n'.join([symbol] +
                                 ['%s: %s' % c for c in components])
            else:
                text = '%s %s' % (symbol, info[10])
            # mark invalid
            if not info[7]:
                text = '<strike>%s</strike>' % text
            # rows.append(text, photo))
            rows.append(Table([[photo], [center_par(text)]], style=TableStyle(
                [('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                 # ('GRID', (0, 0), (-1, -1), 0.5, 'black'),
                 # ('BACKGROUND', (0, 0), (-1, -1), 'cornflowerblue'),
                 ])))
        info_columns = 4
        ci_rows = codename_rows + information_rows
        if len(ci_rows) < info_columns:
            ci_rows += [''] * (info_columns - len(ci_rows))

        # then locations (with map if possible, with associated address if possible); \U0001f30d
        coords = []
        location_strings = []
        for location in event[3]:
            location_id = location[0]
            location_name = location[1]
            lat = location[2]
            lon = location[3]
            location_strings.append(par('\U0001f30d %s' % location_name))

            l_assocs = ensa.db.get_associations_by_location(location_id)
            address_found = False
            for l_assoc in l_assocs:
                for info in l_assoc[1]:
                    if info[4] == 'address':
                        # get_associations_by_location does not give components
                        # -> we must manually find the values
                        components = [
                            i for i in infos if i[0] == info[0]][0][10]
                        location_strings += format_address(
                            get_valid_by_ids(infos, components, codename_id))
                        address_found = True
                        break
                if address_found:
                    break

            if lat is not None and lon is not None:
                coords.append((lat, lon, location_name))
                lat_str = '%.6f\u00b0 %c' % (abs(lat), 'N' if lat > 0 else 'S')
                lon_str = '%.6f\u00b0 %c' % (abs(lon), 'E' if lon > 0 else 'W')
                location_strings.append('%s %s' % (lat_str, lon_str))

        # create map, load as image
        location_map = None
        if coords:
            with tempfile.NamedTemporaryFile() as f:
                location_map = get_map([c[:2] for c in coords],
                                       [c[2] for c in coords])
                location_map.savefig(
                    f.name + '.png', bbox_inches='tight', pad_inches=0)
                location_map = Image(f.name + '.png')
                # location_map._restrictSize(10*cm, 10*cm)
                location_map._restrictSize(7*cm, 7*cm)
        if location_strings:
            location_row = [
                Table([[Table([[ls] for ls in location_strings]), location_map]], colWidths=[8*cm, 7*cm], style=TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))]
        else:
            location_row = []

        # pdb.set_trace()
        # add the complete timeline entry
        event_tables.append(
            Table([[Paragraph('%s - %s (#%d)' % (event_time, event_name, event_id), styles['Heading3'])]]
                  + [[r] for r in time_rows]
                  + [[Table(
                      [[r for r in ci_rows][i:i+info_columns] for i in range(0, len(ci_rows), info_columns)], style=TableStyle([
                          # ('GRID', (0, 0), (-1, -1), 0.5, 'black'),
                      ]))]]
                  + [location_row],
                  # style=TableStyle([
                  #    ('GRID', (0, 0), (-1, -1), 0.5, 'black'),
                  # ])
                  )
        )

    if event_tables:
        entries.append(Paragraph('Timeline', styles['Heading2']))
        entries.append(
            Table([[et] for et in event_tables],
                  colWidths=[16*cm],
                  style=TableStyle([
                      # ('GRID', (0, 0), (-1, -1), 0.5, 'gray'),
                      ('LINEBELOW', (0, 0), (-1, -1), 0.5, 'gray'),
                  ])
                  ),
        )

    """ big map of all associated locations """
    # TODO (also with comments?)
    coords = []
    location_associations = ensa.db.get_associations_by_subject(
        organization_list + [codename])
    for association in location_associations:
        for location in association[3]:
            location_name = location[1]
            lat = location[2]
            lon = location[3]
            if lat is not None and lon is not None:
                coords.append((lat, lon, location_name))
    if coords:
        with tempfile.NamedTemporaryFile() as f:
            location_map = get_map([c[:2] for c in coords],
                                   [c[2] for c in coords])
            location_map.savefig(
                f.name + '.png', bbox_inches='tight', pad_inches=0)
            location_map = Image(f.name + '.png')
            location_map._restrictSize(16*cm, 16*cm)
        entries.append(KeepTogether([
            Paragraph('Action map', styles['Heading2']),
            location_map
        ]))

    """ gallery """
    if own_images:
        entries.append(Paragraph('Gallery', styles['Heading2']))
        images_dict = {}
        for image in own_images:
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
            if not imgs_in_category:
                continue
            t = (Table([imgs_in_category[i:i+columns]
                        for i in range(0, len(imgs_in_category), columns)],
                       hAlign='LEFT',
                       style=TableStyle([
                           # ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                           ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                       ])))
            entries.append(KeepTogether([heading, t]))
    """ all (unused) informations with comments and keywords for codename_id"""
    # TODO

    """ build PDF from individual entries"""
    doc.build(entries)

#####

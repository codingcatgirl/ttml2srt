import re
import sys
from datetime import timedelta
from xml.etree import ElementTree as ET

filename = sys.argv[1]

tree = ET.parse(filename)
root = tree.getroot()

# strip namespaces
for elem in root.iter():
    elem.tag = elem.tag.split('}', 1)[-1]
    elem.attrib = {name.split('}', 1)[-1]: value for name, value in elem.attrib.items()}

tick_rate = root.attrib.get('tickRate', None)
if tick_rate is not None:
    tick_rate = int(tick_rate)

# get styles
styles = {}
for elem in root.findall('./head/styling/style'):
    style = {}
    if 'color' in elem.attrib:
        color = elem.attrib['color']
        if color not in ('#FFFFFF', '#000000'):
            style['color'] = color
    if 'fontStyle' in elem.attrib:
        fontstyle = elem.attrib['fontStyle']
        if fontstyle in ('italic', ):
            style['fontstyle'] = fontstyle
    styles[elem.attrib['id']] = style

body = root.find('./body')

# parse correct start and end times
def parse_time_expression(expression, default_offset=timedelta(0)):
    offset_time = re.match(r'^([0-9]+(\.[0-9]+)?)(h|m|s|ms|f|t)$', expression)
    if offset_time:
        time_value, fraction, metric = offset_time.groups()
        time_value = float(time_value)
        if metric == 'h':
            return default_offset + timedelta(hours=time_value)
        elif metric == 'm':
            return default_offset + timedelta(minutes=time_value)
        elif metric == 's':
            return default_offset + timedelta(seconds=time_value)
        elif metric == 'ms':
            return default_offset + timedelta(milliseconds=time_value)
        elif metric == 'f':
            raise NotImplementedError('Parsing time expressions by frame is not supported!')
        elif metric == 't':
            if tick_rate is None:
                raise NotImplementedError('Time expression contains ticks but tickRate is not specified!')
            return default_offset + timedelta(seconds=time_value/tick_rate)


    clock_time = re.match(r'^([0-9]{2,}):([0-9]{2,}):([0-9]{2,}(\.[0-9]+)?)$', expression)
    if clock_time:
        hours, minutes, seconds, fraction = clock_time.groups()
        return timedelta(hours=int(hours), minutes=int(minutes), seconds=float(seconds))

    clock_time_frames = re.match(r'^([0-9]{2,}):([0-9]{2,}):([0-9]{2,}):([0-9]{2,}(\.[0-9]+)?)$', expression)
    if clock_time_frames:
        raise NotImplementedError('Parsing time expressions by frame is not supported!')

    raise ValueError('unknown time expression: %s' % expression)

def parse_times(elem, default_begin=timedelta(0)):
    if 'begin' in elem.attrib:
        begin = parse_time_expression(elem.attrib['begin'], default_offset=default_begin)
    else:
        begin = default_begin
    elem.attrib['{abs}begin'] = begin

    end = None
    if 'end' in elem.attrib:
        end = parse_time_expression(elem.attrib['end'], default_offset=default_begin)

    dur = None
    if 'dur' in elem.attrib:
        dur = parse_time_expression(elem.attrib['dur'])

    if dur is not None:
        if end is None:
            end = begin + dur
        else:
            end = min(end, begin + dur)

    elem.attrib['{abs}end'] = end

    for child in elem:
        parse_times(child, default_begin=begin)

parse_times(body)

timestamps = set()
for elem in body.findall('.//*[@{abs}begin]'):
    timestamps.add(elem.attrib['{abs}begin'])

for elem in body.findall('.//*[@{abs}end]'):
    timestamps.add(elem.attrib['{abs}end'])

timestamps.discard(None)

# render subtitles on each timestamp
def render_subtitles(elem, timestamp, parent_style={}):
    global styles

    if timestamp < elem.attrib['{abs}begin']:
        return ''
    if elem.attrib['{abs}end'] is not None and timestamp >= elem.attrib['{abs}end']:
        return ''

    result = ''

    style = parent_style.copy()
    if 'style' in elem.attrib:
        style.update(styles.get(elem.attrib['style'], {}))

    if 'color' in elem.attrib:
        style['color'] = elem.attrib['color']

    if 'fontStyle' in elem.attrib:
        style['fontstyle'] = elem.attrib['fontStyle']

    if 'color' in style:
        result += '<font color="%s">' % style['color']

    if style.get('fontstyle') == 'italic':
        result += '<i>'

    if elem.text:
        #result += elem.text.strip()
        result += re.sub(r'\s+$', ' ', re.sub(r'^\s+', ' ', elem.text))
    if len(elem):
        for child in elem:
            result += render_subtitles(child, timestamp)
            if child.tail:
                result += re.sub(r'\s+$', ' ', re.sub(r'^\s+', ' ', child.tail))

    result_stripped = result #.rstrip()
    trailing_whitespaces = result[len(result_stripped):]
    result = result_stripped

    if 'color' in style:
        result += '</font>'

    if style.get('fontstyle') == 'italic':
        result += '</i>'

    result += trailing_whitespaces

    result = re.sub(r'(?P<all>(\s|^)<(font color="([^"]+)"|i)>) +', '\g<all>', result)
    result = re.sub(r' +(?P<all></(font|i)>(\s|$))', '\g<all>', result)
    result = re.sub(r'\n\s+', '\n', result)
    result = re.sub(r'\s+\n', '\n', result)

    result = re.sub(r'<font color="(?P<color1>[^"]+)">(?P<startspaces>\s*)<font color="(?P<color2>[^"]+)">(?P<text>[^<]+)</font>(?P<endspaces>\s*)</font>',
                    r'\g<startspaces><font color="\g<color2>">\g<text></font>\g<endspaces>',
                    result)

    result = re.sub(r'\n+(?P<all></(font|i)>)', '\g<all>\n', result)

    result = re.sub(r'<font color="([^"]+)">(?P<spaces>\s*)</font>', '\g<spaces>', result)

    if elem.tag in ('div', 'p', 'br'):
        result += '\n'

    return result

rendered = []
for timestamp in sorted(timestamps):
    rendered.append((timestamp, re.sub(r'\n\n\n+', '\n\n', render_subtitles(body, timestamp)).strip()))

if not rendered:
    exit(0)

# group timestamps together if nothing changes
rendered_grouped = []
last_text = None
for timestamp, content in rendered:
    if content != last_text:
        rendered_grouped.append((timestamp, content))
    last_text = content

# output srt
rendered_grouped.append((rendered_grouped[-1][0]+timedelta(hours=24), ''))

def format_timestamp(timestamp: timedelta):
    return ('%02d:%02d:%06.3f' % (timestamp.total_seconds()//3600,
                                  timestamp.total_seconds()//60%60,
                                  timestamp.total_seconds()%60)).replace('.', ',')


srt_i = 1
for i, (timestamp, content) in enumerate(rendered_grouped[:-1]):
    if content == '':
        continue
    print(srt_i)
    print(format_timestamp(timestamp)+' --> '+format_timestamp(rendered_grouped[i+1][0]))
    print(content)
    srt_i += 1
    print('')


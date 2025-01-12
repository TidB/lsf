import datetime
import json
import pathlib
import re
import time
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

NORMAL_ROOMS = (1013, 1033, 1030, 999)


def get_room_list() -> dict[str, str]:
    rooms = {}

    cache = pathlib.Path('cached_room_list.html')
    if cache.exists():
        print('using room list cache')
        html = cache.read_text(encoding='utf-8')
    else:
        print('no room list cache, requesting')
        response = requests.get('https://www.lsf.tu-dortmund.de/qisserver/rds?state=wsearchv&search=3&choice.k_campus.id=y&k_raumart.raumartid=1,15&k_campus.id=3&P_start=0&P_anzahl=100&_form=display')
        html = response.text
        cache.write_text(html, encoding='utf-8')

    soup = BeautifulSoup(html, features='html.parser')
    for line in soup.select('.functionnavi'):
        entry = line.find_next_sibling('div').find_next('a')
        link = entry['href']
        url = urlparse(link)
        *room_name, typ = re.split(r',\s+', entry.get_text().strip(), )
        building_entry = entry.parent.find_next_sibling('div').find_next_sibling('div').get_text().strip().split()
        building_name = ' '.join(building_entry[1:]).replace('Geschoßbau', 'GB')
        rooms[parse_qs(url.query)['raum.rgid'][0]] = f'{building_name} {" ".join(room_name)} ({typ[0]})'

    return rooms


def get_correct_column(naive_column: int, row: int, offsets) -> int:
    # Get the first, second, nth 0 and its location (n = naive_column)
    # n basically says how many 0s we should skip because those places would be occupied by lower ns
    if naive_column == 0:
        return 0

    i = 0
    how_many_to_skip = naive_column - 1
    for i, offset in enumerate(offsets[row]):
        if i == 1:  # Ignore the lil boxes
            continue
        if offset == 0:
            if how_many_to_skip == 0:
                break
            else:
                how_many_to_skip -= 1
    #r = naive_column + sum(offsets[row][:naive_column])
    #print(f'naive: {naive_column}, new: {r}')
    return i


def row_to_time(row: int) -> str:
    if row == 0:
        return 'NO'
    elif row == 1:
        return 'vor 8'
    else:
        return f'{8 + (row-2) // 4}:{(row-2) % 4 * 15:02}'


def get_room_occupancy(id: str, week: int, year: int):
    cache = pathlib.Path(f'cache/{id}.html')
    if cache.exists():
        print('using room cache')
        html = cache.read_text(encoding='utf-8')
    else:
        print('no room cache, requesting')
        response = requests.post(
            'https://www.lsf.tu-dortmund.de/qisserver/rds?',
            params={
                'state': 'wplan',
                'act': 'Raum',
                'pool': 'Raum',
                'P.subc': 'plan',
                'raum.rgid': id,
                #'purge': 'n', 'getglobal': 'n',
            },
            data={'week': f'{week}_{year}', 'work': 'anzeigen'}
        )
        html = response.text
        cache.write_text(html, encoding='utf-8')
        time.sleep(5)

    soup = BeautifulSoup(html, features='html.parser')
    timetable = soup.find('table', {'border': '1'})
    free_times = {}

    rowspans = [[0] * 9 for _ in range(12 * 4 + 3)]  # 1 means that a cell is covered by a rowspan from above
                      # 9 for seven days + the previous two time columns
                                                # 3 for the rows before 8, after 20 and the top time
    for i, row in enumerate(timetable.findChildren('tr', recursive=False)):
        if i == 0:  # weekday row
            continue

        for j, column in enumerate(row.findChildren('td', recursive=False)):
            if (
                    (column.has_attr('class') and {'plan2', 'plan5', 'plan_rahmen'} & set(column['class']))
                    or (column.has_attr('width') and column['width'] == '0')
            ):
                if column.has_attr('rowspan') and column.get_text().strip() != 'ab  20':  # The last row for some reason still specifies rowspan 4
                    blocked_slots = int(column['rowspan'])
                    for k in range(1, blocked_slots):  # Skipping the first because the first row of the rowspan isn't affected
                        if rowspans[i + k][get_correct_column(j, i, rowspans)] == 1:
                            print('uh oh, there seem to be two overlapping rowspans, this shouldn\'t happen')
                        rowspans[i + k][get_correct_column(j, i, rowspans)] = 1

            if column.has_attr('class') and 'plan1' in column['class']:
                day = get_correct_column(j, i, rowspans) - 2
                if day not in free_times:
                    free_times[day] = []
                free_times[day].append(i)

    # Compress to time ranges, represented by tuples
    free_ranges = {day: [] for day in free_times}
    for day, free_slots in free_times.items():
        current_range = None
        last_slot = None
        for slot in free_slots:
            # Discard 1 and 50 times (before 8 and after 20)
            if slot in (1, 50):
                continue

            if current_range is None:
                current_range = (slot, None)
            elif slot - last_slot > 1:
                if last_slot - current_range[0] < 4:
                    print(f'range {(current_range[0], last_slot)} too small, ignored')
                else:
                    free_ranges[day].append((current_range[0], last_slot))
                current_range = (slot, None)
            last_slot = slot
        if current_range is not None:
            if last_slot - current_range[0] < 4:
                print(f'range {(current_range[0], last_slot)} too small, ignored')
            else:
                free_ranges[day].append((current_range[0], last_slot))

    return free_ranges


def fill_html(stuff):
    template = pathlib.Path('index.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(template, features='html.parser')
    table = soup.find(class_='links')
    table.append(BeautifulSoup(stuff, features='html.parser'))
    pathlib.Path('index_old.html').write_text(soup.prettify())


def gen_table(free_ranges):
    DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    body = """<table class="language-table">
                <thead>
                <tr>
                    <th>day</th>
                    <th>free</th>
                </tr>
                </thead>
                <tbody>"""
    for day, ranges in free_ranges.items():
        if day > 4:
            continue
        body += '<tr>'
        body += f'<td>{DAYS[day]}</td>'
        body += f'<td>{", ".join(row_to_time(r[0])+"–"+row_to_time(r[1]+1) for r in ranges)}</td>'
        body += '</tr>'
    body += "</tbody></table>"
    return body

if __name__ == '__main__':
    rooms = get_room_list()
    file = {'room_names': {}}
    free_rooms = {}
    today = datetime.date.today().isocalendar()
    week_start = datetime.date.fromisocalendar(
        today.year,
        today.week+(1 if today.weekday > 5 else 0),
        day=1
    ).isocalendar()
    print(rooms)

    for id, name in rooms.items():
        #if int(id) not in NORMAL_ROOMS:
        #    print(f'skipping {id}')
        #    continue

        print(f'processing room {id} ({name})')
        free_rooms[id] = get_room_occupancy(id, week_start.week, week_start.year)
        file['room_names'][id] = name

    file['room_order'] = [key for key, _ in sorted(rooms.items(), key=lambda x: x[1])]
    file['updated'] = datetime.datetime.now().isoformat()
    file['week_start'] = datetime.date.fromisocalendar(*week_start).isoformat()
    file['free_rooms'] = free_rooms
    with open('free.json', 'w', encoding='utf-8') as f:
        json.dump(file, f)

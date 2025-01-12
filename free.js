NORMAL_ROOMS = [1013, 1030, 1033, 1035, 1042, 1066, 2260, 4385, 4608, 4610, 4628, 999];

Date.prototype.addDays = function(days) {
    var date = new Date(this.valueOf());
    date.setDate(date.getDate() + days);
    return date;
}

function to_time(int) {
    return (8 + Math.floor((int-2) / 4)).toString().padStart(2, '0') + ':' + (((int-2) % 4) * 15).toString().padStart(2, '0');
}

function time_to_slot() {
    var date = new Date();
    var dec = date.getHours() + (date.getMinutes() / 60);
    var adjusted = Math.floor((dec - 7.5) * 4);
    return adjusted;
}

function main(data) {
    document.getElementById('updated').innerHTML = data['updated'];
    roomselect = document.getElementById('room-select').addEventListener("change", (event) => update_buttons(data, dayselect.selectedIndex));
    dayselect = document.getElementById('day-select');
    dayselect.addEventListener("change", (event) => update_buttons(data, dayselect.selectedIndex));
    week_start = new Date(Date.parse(data['week_start']));
    for (let i=0; i<5; i++) {
        day = week_start.addDays(i)
        dayselect.innerHTML += '<option>' + day.toLocaleDateString('de-DE', {weekday: 'long', day: 'numeric', month: 'short'}) + '</option>'
    }

    let current_day = Math.max((new Date()).getDay(), 5) - 1;
    dayselect.selectedIndex = current_day;
    update_buttons(data, current_day.toString());
}

function update_buttons(data, index) {
    only_normal_rooms = document.getElementById('room-select').selectedIndex == 0;
    table.innerHTML = "";
    let current_day = index;//(index - 1) % 7
    table = document.getElementById('table');
    current_hour_slot = time_to_slot();
    data['room_order'].forEach(function(room_id) {
        if (only_normal_rooms && !NORMAL_ROOMS.includes(Number(room_id))) {
            return;
        }10
        var link = 'https://www.lsf.tu-dortmund.de/qisserver/rds?state=wplan&act=Raum&pool=Raum&P.subc=plan&raum.rgid=' + room_id;
        let row = '<tr><td><a title="im LSF öffnen" class="lsf-link" href="' + link + '">🔗</a> ' + data['room_names'][room_id] + '</td>';
        let slots = [];
        data['free_rooms'][room_id][current_day].forEach(function(slot) {
            if (slot[0] === 2 && slot[1] === 49) {
                slots.push('<i>ganztägig frei</i>')
            } else {
                var span = to_time(slot[0]) + '–' + to_time(slot[1]+1);
                if (current_hour_slot >= slot[0] && (current_hour_slot + 4) <= slot[1]) {
                    span = '<strong>' + span + '</strong>';
                } else if ((current_hour_slot + 2) >= slot[1]) {
                    span = '<span class="faded-time">' + span + '</span>';
                }
                slots.push(span)
            }
        });
        if (slots.length === 0) {
            row += '<td><i>keine freien Slots</i></td></tr>';
        } else {
            row += '<td>' + slots.join(', ') + '</td></tr>';
            table.innerHTML += row;
        }
    })
}
var request = new XMLHttpRequest();
request.open('GET', 'https://mismeasu.red/lsf/free.json');
request.responseType = 'json';
request.onload = function(e) {
    if (this.status == 200) {
        main(this.response)
    }
}
request.send()
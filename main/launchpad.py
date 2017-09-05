# I hate Python.

from copy import copy
from mididings import *
import mididings.event as mididings_event
import mididings.util as mididings_util

# Using Novation's Session Layout (ID=0x00)
# This sysex is for setting-up the Session mode on Launchpad Mini:
# SysEx((0xf0, 0x00, 0x20, 0x29, 0x2, 0x18, 0x22, 0, 0xf7))

# CC numbers:
CC_PEDAL = 64

# Launchpad LED codes:
LED_OFF = 4
RED1    = 5
RED2    = 6
RED3    = 7
GREEN1  = 20
GREEN2  = 36
GREEN3  = 52

CTRL_RANGE = range(0, 8)
PAGE_RANGE = range(0, 8)
MATRIX_RANGE_X = range(0, 8)
MATRIX_RANGE_Y = range(0, 8)

# Return CC number that corresponds to the top button.
def ctrl_button_id(x):
    return 0x68 + x

def x_for_ctrl_cc(cc):
    return cc - 0x68

def page_button_id(y):
    return matrix_button_id(8, y)

def y_for_page_note(note):
    return y_for_matrix_note(note)

# Use for setting button color.
# Return note-on number corresponding to given matrix button.
# Includes circular buttons on the far right side.
# column is [0..8], row is [0..7]
def matrix_button_id(x, y):
    return (y << 4) | (x & 0b1111)

def x_for_matrix_note(note):
    return note & 0b1111

def y_for_matrix_note(note):
    return (note >> 4) & 0b1111

CTRL_BUTTONS = { ctrl_button_id(x): True for x in CTRL_RANGE }
PAGE_BUTTONS = { page_button_id(y): True for y in PAGE_RANGE }
MATRIX_BUTTONS = { matrix_button_id(x, y): True for x in MATRIX_RANGE_X for y in MATRIX_RANGE_Y }

class Launchpad:
    PRESS = 'press'
    RELEASE = 'release'

    def __init__(this, control_input_port, control_output_port, clock_input_port=None):
        this.windows = []
        this.control_input_port = mididings_util.port_number(control_input_port)
        this.control_output_port = mididings_util.port_number(control_output_port)
        this.clock_input_port = mididings_util.port_number(clock_input_port)
        # Map button ID (ctrl_button_id(x)) to color:
        this.ctrl_state = [LED_OFF for x in CTRL_RANGE]
        this.previous_ctrl_state = [LED_OFF for x in CTRL_RANGE]
        # Map button ID (page_button_id(y)) to color:
        this.page_state = [LED_OFF for y in PAGE_RANGE]
        this.previous_page_state = [LED_OFF for y in PAGE_RANGE]
        # Map button ID (matrix_button_id(x, y)) to color:
        this.matrix_state = [[LED_OFF for y in MATRIX_RANGE_Y] for x in MATRIX_RANGE_X]
        this.previous_matrix_state = [[LED_OFF for y in MATRIX_RANGE_Y] for x in MATRIX_RANGE_X]

    def chain(this):
        return Process(this.process)

    def add_window(this, window):
        this.windows.append(window)

    def process(this, event):
        events = this.process_windows(event)
        this.collect_buttons_state()
        events += this.generate_led_events()
        return events

    def process_windows(this, event):
        events = []
        if event.port == this.control_input_port:
            if event.type == CTRL:
                # Ctrl button?
                if event.ctrl in CTRL_BUTTONS:
                    x = x_for_ctrl_cc(event.ctrl)
                    for window in this.windows:
                        if x in window.allocated_ctrl_buttons:
                            events += window.ctrl_button_event(x, this.PRESS if event.value == 127 else this.RELEASE)
            elif event.type in (NOTEON, NOTEOFF):
                # Page button?
                if event.note in PAGE_BUTTONS:
                    y = y_for_page_note(event.note)
                    for window in this.windows:
                        if y in window.allocated_page_buttons:
                            events += window.page_button_event(y, this.PRESS if event.type == NOTEON else this.RELEASE)
                # Matrix button?
                if event.note in MATRIX_BUTTONS:
                    gx = x_for_matrix_note(event.note)
                    gy = y_for_matrix_note(event.note)
                    for window in this.windows:
                        lx = gx - window.rect.x
                        ly = gy - window.rect.y
                        if lx in range(0, window.rect.w) and ly in range(0, window.rect.h):
                            events += window.matrix_button_event(lx, ly, this.PRESS if event.type == NOTEON else this.RELEASE)
        else:
            for window in this.windows:
                events += window.process(event)
        return events

    # Update state of the buttons by merging states of windows.
    def collect_buttons_state(this):
        for window in this.windows:
            for x in CTRL_RANGE:
                if x in window.allocated_ctrl_buttons:
                    this.ctrl_state[x] = window.ctrl_state[x]
            for y in PAGE_RANGE:
                if y in window.allocated_page_buttons:
                    this.page_state[y] = window.page_state[y]
            for y in window.range_y:
                for x in window.range_x:
                    gx = window.rect.x + x
                    gy = window.rect.y + y
                    this.matrix_state[gx][gy] = window.matrix_state[x][y]

    # Generate MIDI events for current state of the buttons.
    def generate_led_events(this):
        events = []
        # Update top buttons' row:
        for x in CTRL_RANGE:
            if this.ctrl_state[x] != this.previous_ctrl_state[x]:
                color = this.ctrl_state[x]
                events += this.set_ctrl_button(x, color)
        # Update page buttons:
        for y in PAGE_RANGE:
            if this.page_state[y] != this.previous_page_state[y]:
                color = this.page_state[y]
                events += this.set_page_button(y, color)
        # Update matrix:
        for y in MATRIX_RANGE_Y:
            for x in MATRIX_RANGE_X:
                if this.matrix_state[x][y] != this.previous_matrix_state[x][y]:
                    color = this.matrix_state[x][y]
                    events += this.set_matrix_button(x, y, color)
        # Swaps:
        this.previous_ctrl_state, this.ctrl_state = this.ctrl_state, this.previous_ctrl_state
        this.previous_page_state, this.page_state = this.page_state, this.previous_page_state
        this.previous_matrix_state, this.matrix_state = this.matrix_state, this.previous_matrix_state
        return events

    def set_ctrl_button(this, x, color):
        return [mididings_event.CtrlEvent(this.control_output_port, 1, ctrl_button_id(x), color)]

    def set_page_button(this, y, color):
        return this.set_matrix_button(8, y, color)

    def set_matrix_button(this, x, y, color):
        return [mididings_event.NoteOnEvent(this.control_output_port, 1, matrix_button_id(x, y), color)]

class Rect:
    def __init__(this, x, y, w, h):
        this.x = x
        this.y = y
        this.w = w
        this.h = h

    def translated(this, x, y):
        return Rect(this.x + x, this.y + y, this.w, this.h)

class Window:
    def __init__(this, rect):
        this.rect = rect
        this.range_x = range(0, rect.w)
        this.range_y = range(0, rect.h)
        this.ctrl_state = [LED_OFF for x in CTRL_RANGE]
        this.page_state = [LED_OFF for y in PAGE_RANGE]
        this.matrix_state = [[LED_OFF for y in this.range_y] for x in this.range_x]
        this.allocated_ctrl_buttons = []
        this.allocated_page_buttons = []

    def process(this, event):
        return []

    # type can be Launchpad.PRESS or Launchpad.RELEASE.
    def ctrl_button_event(this, x, type):
        return []

    # type can be Launchpad.PRESS or Launchpad.RELEASE.
    def page_button_event(this, y, type):
        return []

    # x, y is button position.
    # type can be Launchpad.PRESS or Launchpad.RELEASE.
    def matrix_button_event(this, x, y, type):
        return []

class WindowSwitcher(Window):
    def __init__(this, rect, scroll_page_button=None):
        Window.__init__(this, rect)
        this.scroll_page_button = scroll_page_button
        this.current_window_index = 0
        this.windows = []
        this.page_to_index = {}
        this.scroll_pressed = False

    def add_window(this, window, page=None):
        if page != None:
            this.page_to_index[page] = len(this.windows)
        this.windows.append(window)
        this.set_current_window_index(0)

    def process(this, event):
        events = []
        for window in this.windows:
            events += window.process(event)
        this.draw_window()
        return events

    def ctrl_button_event(this, x, type):
        events = this.current_window().ctrl_button_event(x, type)
        this.draw_window()
        return events

    def page_button_event(this, y, type):
        events = []
        if y in this.page_to_index.keys():
            if type == Launchpad.PRESS:
                this.set_current_window_index(this.page_to_index[y])
        elif y == this.scroll_page_button:
            if type == Launchpad.PRESS:
                this.set_current_window_index((this.current_window_index + 1) % len(this.windows))
            this.scroll_pressed = type == Launchpad.PRESS
        else:
            events = this.current_window().page_button_event(y, type)
        this.draw_window()
        return events

    def matrix_button_event(this, x, y, type):
        events = this.current_window().matrix_button_event(x, y, type)
        this.draw_window()
        return events

    def draw_window(this):
        window = this.current_window()
        for x in window.allocated_ctrl_buttons:
            this.ctrl_state[x] = window.ctrl_state[x]
        for y in window.allocated_page_buttons:
            this.page_state[y] = window.page_state[y]
        for y in this.range_y:
            for x in this.range_x:
                this.matrix_state[x][y] = window.matrix_state[x][y]
        # Own 'scroll button':
        if this.scroll_page_button:
            this.page_state[this.scroll_page_button] = GREEN3 + RED3 if this.scroll_pressed else LED_OFF

    def set_current_window_index(this, index):
        this.current_window_index = index
        this.allocated_ctrl_buttons = copy(this.current_window().allocated_ctrl_buttons)
        this.allocated_page_buttons = copy(this.current_window().allocated_page_buttons)
        this.allocated_page_buttons.append(this.scroll_page_button)
        this.draw_window()

    def current_window(this):
        return this.windows[this.current_window_index]

class ChannelRouter(Window):
    NOTE_PRESSED = 'pressed'
    NOTE_SUSTAINED = 'sustained'
    LIGHT_UP_ACTIVE_COLOR = GREEN3 + RED3
    LIGHT_UP_INACTIVE_COLOR = GREEN3 + RED1
    LIGHT_UP_TIME = 3

    def __init__(this, rect, input_port, input_channel, output_port, active_color=RED3, inactive_color_odd=GREEN1, inactive_color_even=GREEN1):
        Window.__init__(this, rect)
        this.input_port = mididings_util.port_number(input_port)
        this.output_port = mididings_util.port_number(output_port)
        this.input_channel = input_channel
        this.selected_channel = 1
        this.highlighted_channels = {channel: 0 for channel in range(1, 17)}
        # Note-on events are stored per channel, and if selected channel changes and note-offs are sent,
        # they are also sent to the already sounding notes.
        this.noteons = {channel: {} for channel in range(1, 17)}
        this.sustains = {channel: 0 for channel in range(1, 17)}
        this.active_color = active_color
        this.inactive_color_odd = inactive_color_odd
        this.inactive_color_even = inactive_color_even
        this.update_colors()

    def process(this, event):
        events = []
        if event.port == this.input_port:
            if event.type != SYSRT_CLOCK:
                print event
            # Route data from configured input channel:
            if event.channel == this.input_channel:
                events += this.track_notes(event)
                event.port = this.output_port
                event.channel = this.selected_channel
                events.append(event)
            # Route all events on channels other than configured back to the synth:
            elif event.type != SYSRT_CLOCK: # TODO enableable with a CTRL button
                event.port = this.output_port
                events.append(event)
            # Blink a button on Note-on events:
            if event.type == NOTEON:
                this.highlighted_channels[event.channel] = this.LIGHT_UP_TIME
        if event.type == SYSRT_CLOCK:
            for i in range(1, 17):
                if this.highlighted_channels[i] > 0:
                    this.highlighted_channels[i] -= 1
        this.update_colors()
        return events

    def track_notes(this, event):
        events = []
        if event.type == NOTEON:
            this.noteons[this.selected_channel][event.note] = this.NOTE_PRESSED
        elif event.type == NOTEOFF:
            for channel, notes in this.noteons.iteritems():
                if channel != this.selected_channel and notes.get(event.note) == this.NOTE_PRESSED:
                    del notes[event.note]
                    events.append(mididings_event.NoteOffEvent(this.output_port, channel, event.note))
        elif event.type == CTRL and event.ctrl == CC_PEDAL:
            this.sustains[this.selected_channel] = event.value
            for channel, pedal_value in this.sustains.iteritems():
                if channel != this.selected_channel and pedal_value > 0:
                    this.sustains[channel] = event.value
                    events.append(mididings_event.CtrlEvent(this.output_port, channel, CC_PEDAL, event.value))
        return events

    def matrix_button_event(this, x, y, type):
        events = []
        if type == Launchpad.PRESS:
            pedal_value = this.sustains[this.selected_channel]
            this.selected_channel = y * this.rect.w + x + 1
            # If pedal was depressed before switching, transfer its CC value to
            # the new channel:
            if pedal_value > 0:
                this.sustains[this.selected_channel] = pedal_value
                events.append(mididings_event.CtrlEvent(this.output_port, this.selected_channel, CC_PEDAL, pedal_value))
            print "ChannelRouter: switched to channel %d" % this.selected_channel
            this.update_colors()
        return events

    def update_colors(this):
        for y in this.range_y:
            for x in this.range_x:
                channel = y * this.rect.w + x + 1
                active = channel == this.selected_channel
                color = this.active_color if active else this.color_for_x(x, y)
                if this.highlighted_channels[channel] > 0:
                    color = this.LIGHT_UP_ACTIVE_COLOR if active else this.LIGHT_UP_INACTIVE_COLOR
                this.matrix_state[x][y] = color

    def color_for_x(this, x, y):
        z = y * this.rect.w + x
        return this.inactive_color_odd if z % 2 == 0 else this.inactive_color_even

class PatternTrigger(Window):
    MANUAL = 'manual'
    ONCE = 'once'
    LIGHT_UP_TIME = 25
    PAGE_ACTIVE_COLOR = GREEN3
    PAGE_INACTIVE_COLOR = RED1
    PAUSE_BLINK_TIME = 48
    PREPARE_BLINK_TIME = 24
    PREPARE_ACTIVE_COLOR = GREEN3 + RED3
    MODE_PREPARE = 'prepare'
    MODE_SAVE = 'save'
    MODE_LOAD = 'load'

    class MidiConfig:
        def __init__(this, first_key, output_port, output_channel):
            this.first_key = first_key
            this.output_port = mididings_util.port_number(output_port)
            this.output_channel = output_channel

        def create_event(this, type):
            return mididings_event.MidiEvent(type, port=this.output_port, channel=this.output_channel)

    class Page:
        def __init__(this, midi_config, rect, range_x, range_y):
            this.midi_config = midi_config
            this.rect = rect
            this.range_x = range_x
            this.range_y = range_y
            this.running_patterns = [[0 for y in this.range_y] for x in this.range_x]

        def start_or_stop_rpprs(this, start):
            events = []
            for y in this.range_y:
                for x in this.range_x:
                    if this.running_patterns[x][y]:
                        events.append(this.create_rppr_event_for(x, y, start))
            return events

        def create_rppr_event_for(this, x, y, start):
            ev = None
            if start:
                ev = this.midi_config.create_event(NOTEON)
                ev.velocity = 127
            else:
                ev = this.midi_config.create_event(NOTEOFF)
                ev.velocity = 0
            ev.note = this.button_to_key(x, y)
            return ev

        def button_to_key(this, x, y):
            button = y * this.rect.w + x
            return button + this.midi_config.first_key

    def __init__(this, rect, first_key, trigger, output_port, output_channel):
        Window.__init__(this, rect)
        this.midi_config = this.MidiConfig(first_key, output_port, output_channel)
        this.trigger = trigger
        this.running = True
        this.pages = [this.Page(this.midi_config, this.rect, this.range_x, this.range_y) for p in PAGE_RANGE]
        this.current_page_index = 0
        this.mode = None
        this.color_tables = [
            [
                RED1,
                RED1,
                RED1 + GREEN1,
                RED1 + GREEN1,
                RED1 + GREEN1,
                GREEN1,
                GREEN1,
            ],
            [
                RED2,
                RED2 + GREEN1,
                RED2 + GREEN1,
                RED2 + GREEN2,
                RED1 + GREEN2,
                RED1 + GREEN2,
                GREEN2,
            ],
            [
                RED3,
                RED3 + GREEN1,
                RED3 + GREEN2,
                RED3 + GREEN3,
                RED2 + GREEN3,
                RED1 + GREEN3,
                GREEN3,
            ],
        ]
        for ct in this.color_tables:
            ct += list(reversed(ct[1:-1]))
        this.play_button_pos = None
        this.play_button_blink_counter = 0
        # Related to MODE_PREPARE:
        this.prepare_button_pos = None
        this.prepare_button_blink_counter = 0
        this.current_prepare_page_index = 0
        # Related to MODE_SAVE:
        this.save_button_pos = None
        # Related to MODE_LOAD:
        this.load_button_pos = None
        this.update_colors()

    def set_play_button(this, button_pos):
        this.play_button_pos = button_pos
        # Don't run by default, if we have the play button enabled:
        this.running = False
        this.update_ctrl_buttons()

    def set_save_button(this, button_pos):
        this.save_button_pos = button_pos
        this.update_ctrl_buttons()

    def set_load_button(this, button_pos):
        this.load_button_pos = button_pos
        this.update_ctrl_buttons()

    def set_prepare_button(this, button_pos):
        this.prepare_button_pos = button_pos
        this.update_ctrl_buttons()

    def set_page_buttons(this, buttons):
        this.allocated_page_buttons = buttons
        this.update_colors()

    def process(this, event):
        if event.type == SYSRT_CLOCK:
            this.play_button_blink_counter = (this.play_button_blink_counter + 1) % this.PAUSE_BLINK_TIME
            this.prepare_button_blink_counter = (this.prepare_button_blink_counter + 1) % this.PREPARE_BLINK_TIME
            # Fade 'once' buttons:
            if this.trigger == this.ONCE:
                for y in this.range_y:
                    for x in this.range_x:
                        if this.current_page().running_patterns[x][y] in range(1, this.LIGHT_UP_TIME):
                            this.current_page().running_patterns[x][y] -= 1
        this.update_colors()
        return []

    def ctrl_button_event(this, x, type):
        events = []
        if type == Launchpad.PRESS:
            if this.play_button_pos != None and x == this.play_button_pos:
                this.running = not this.running
                events += this.current_page().start_or_stop_rpprs(this.running)
                this.update_colors()
            if this.prepare_button_pos != None and x == this.prepare_button_pos:
                if this.mode == this.MODE_PREPARE:
                    this.mode = None
                else:
                    this.mode = this.MODE_PREPARE
                    this.current_prepare_page_index = this.current_page_index
                this.update_colors()
        return events

    def page_button_event(this, y, type):
        events = []
        # In normal mode, current page is changed.
        if this.mode == None:
            if type == Launchpad.PRESS and y in this.allocated_page_buttons:
                events += this.current_page().start_or_stop_rpprs(False)
                this.current_page_index = y
                events += this.current_page().start_or_stop_rpprs(this.running)
                this.update_colors()
        # In prepare mode, change the current_prepare_page.
        elif this.mode == this.MODE_PREPARE:
            if type == Launchpad.PRESS and y in this.allocated_page_buttons:
                this.current_prepare_page_index = y
                this.update_colors()
        return events

    def matrix_button_event(this, x, y, type):
        events = []
        # Acquire page:
        page = this.current_page_to_modify()
        # Modify the page:
        if page:
            time = page.running_patterns[x][y]
            if this.trigger == this.MANUAL:
                if type == Launchpad.PRESS:
                    time = 0 if time else this.LIGHT_UP_TIME
            elif this.trigger == this.ONCE:
                if type == Launchpad.PRESS:
                    time = this.LIGHT_UP_TIME
                elif type == Launchpad.RELEASE and time in range(1, this.LIGHT_UP_TIME + 1):
                    time -= 1
            page.running_patterns[x][y] = time
            if this.mode == None or (this.mode == this.MODE_PREPARE and page == this.current_page()):
                if (this.trigger == this.MANUAL and type == Launchpad.PRESS) or this.trigger == this.ONCE:
                    if this.running:
                        events.append(page.create_rppr_event_for(x, y, time >= this.LIGHT_UP_TIME))
            this.update_colors()
        return events

    def update_ctrl_buttons(this):
        this.allocated_ctrl_buttons = [
            this.play_button_pos,
            this.save_button_pos,
            this.load_button_pos,
            this.prepare_button_pos,
        ]

    def current_page(this):
        return this.pages[this.current_page_index]

    def current_prepare_page(this):
        return this.pages[this.current_prepare_page_index]

    def current_page_to_modify(this):
        if this.mode == None:
            return this.current_page()
        elif this.mode == this.MODE_PREPARE:
            return this.current_prepare_page()

    def update_colors(this):
        # Ctrl buttons:
        if this.play_button_pos != None:
            c = RED1
            if this.running:
                c = GREEN3
            else:
                if this.play_button_blink_counter > this.PAUSE_BLINK_TIME / 2:
                    c = RED2
            this.ctrl_state[this.play_button_pos] = c
        if this.save_button_pos != None:
            this.ctrl_state[this.save_button_pos] = RED1 if this.mode in (None, this.MODE_SAVE) else LED_OFF
        if this.load_button_pos != None:
            this.ctrl_state[this.load_button_pos] = GREEN1 if this.mode in (None, this.MODE_LOAD) else LED_OFF
        if this.prepare_button_pos != None:
            c = RED1 + GREEN1
            if this.mode == this.MODE_PREPARE:
                c = LED_OFF
                if this.prepare_button_blink_counter > this.PREPARE_BLINK_TIME / 2:
                    c = GREEN3 + RED3
            this.ctrl_state[this.prepare_button_pos] = c
        # Page buttons:
        if this.mode == None:
            for y in this.allocated_page_buttons:
                this.page_state[y] = this.PAGE_INACTIVE_COLOR
            this.page_state[this.current_page_index] = this.PAGE_ACTIVE_COLOR
        elif this.mode == this.MODE_PREPARE:
            for y in this.allocated_page_buttons:
                this.page_state[y] = this.PAGE_INACTIVE_COLOR
            this.page_state[this.current_page_index] = this.PAGE_ACTIVE_COLOR
            this.page_state[this.current_prepare_page_index] = this.PREPARE_ACTIVE_COLOR
        # Matrix:
        page = this.current_page_to_modify()
        for y in this.range_y:
            for x in this.range_x:
                this.matrix_state[x][y] = this.color_for_matrix(page, x, y)

    def color_for_matrix(this, page, x, y):
        color = LED_OFF
        time = page.running_patterns[x][y]
        if time > 0:
            brightness = int(min(2.5 * time / this.LIGHT_UP_TIME, 2))
            color = this.active_color_for_matrix(x, y, brightness)
        return color

    def active_color_for_matrix(this, x, y, brightness=2):
        return this.color_tables[brightness][(y * this.rect.w + x) % len(this.color_tables[brightness])]


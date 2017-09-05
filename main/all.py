#!/usr/bin/env python2

from mididings import *
from launchpad import *

LAUNCHPAD_IN_PORT = 'Launchpad in'
LAUNCHPAD_IN_CHANNEL = 1
LAUNCHPAD_OUT_PORT = 'Launchpad out'
LAUNCHPAD_OUT_CHANNEL = 1

AKAIPADS_IN_PORT = 'Akaipads in'
AKAIPADS_IN_CHANNEL = 1

KRONOS_IN_PORT = 'Kronos in'
KRONOS_IN_CHANNEL = 16
KRONOS_OUT_PORT = 'Kronos out'
KRONOS_OUT_CHANNEL = 16

XKEY_IN_PORT = 'Xkey in'

CLOCK_IN_PORT = 'Clock in'

IN_PORTS=[
    (LAUNCHPAD_IN_PORT, 'Launchpad Mini 15:Launchpad Mini 15 MIDI 1'),
    (KRONOS_IN_PORT, 'KRONOS:KRONOS MIDI 1'),
    (AKAIPADS_IN_PORT, 'MPD226:MPD226 MIDI 1'),
    (XKEY_IN_PORT, 'Xkey:Xkey MIDI 1'),
    (CLOCK_IN_PORT, 'KRONOS:KRONOS MIDI 1'),
]

OUT_PORTS=[
    (LAUNCHPAD_OUT_PORT, 'Launchpad Mini 15:Launchpad Mini 15 MIDI 1'),
    (KRONOS_OUT_PORT, 'KRONOS:KRONOS MIDI 1'),
]

config(in_ports=IN_PORTS, out_ports=OUT_PORTS)

pattern_trigger_manual = PatternTrigger(Rect(4, 0, 4, 6), first_key=37, trigger=PatternTrigger.MANUAL, output_port=KRONOS_OUT_PORT, output_channel=KRONOS_OUT_CHANNEL)
pattern_trigger_manual.set_play_button(6)
pattern_trigger_manual.set_prepare_button(7)
pattern_trigger_manual.set_save_button(0) # TODO
pattern_trigger_manual.set_load_button(1) # TODO
pattern_trigger_manual.set_page_buttons([0, 1, 2, 3, 4, 5, 6])
pattern_trigger_once = PatternTrigger(Rect(0, 0, 4, 6), first_key=37 + 24, trigger=PatternTrigger.ONCE, output_port=KRONOS_OUT_PORT, output_channel=KRONOS_OUT_CHANNEL)

routers_rect = Rect(0, 0, 8, 2)
kronos_router = ChannelRouter(routers_rect, input_port=KRONOS_IN_PORT, input_channel=KRONOS_IN_CHANNEL, output_port=KRONOS_OUT_PORT)
akaipads_router = ChannelRouter(routers_rect, input_port=AKAIPADS_IN_PORT, input_channel=AKAIPADS_IN_CHANNEL, output_port=KRONOS_OUT_PORT,
                                active_color=GREEN3, inactive_color_odd=RED1, inactive_color_even=RED1)

routers_switch = WindowSwitcher(routers_rect.translated(0, 6), scroll_page_button=7)
routers_switch.add_window(kronos_router)
routers_switch.add_window(akaipads_router)

launchpad = Launchpad(LAUNCHPAD_IN_PORT, LAUNCHPAD_OUT_PORT, CLOCK_IN_PORT)
launchpad.add_window(pattern_trigger_manual)
launchpad.add_window(pattern_trigger_once)
launchpad.add_window(routers_switch)

run(launchpad.chain())


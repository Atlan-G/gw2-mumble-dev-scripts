#!/usr/bin/python
import ctypes
import mmap
import time
import signal
import sys
import keyboard
import math

CURRENT_POS = None
CURRENT_MAP = None
MARKER_MAP = None
LINE_MARKER = [None, None]

class Link(ctypes.Structure):
    _fields_ = [
        ("uiVersion", ctypes.c_uint32),           # 4 bytes
        ("uiTick", ctypes.c_ulong),               # 4 bytes
        ("fAvatarPosition", ctypes.c_float * 3),  # 3*4 bytes
        ("fAvatarFront", ctypes.c_float * 3),     # 3*4 bytes
        ("fAvatarTop", ctypes.c_float * 3),       # 3*4 bytes
        ("name", ctypes.c_wchar * 256),           # 512 bytes
        ("fCameraPosition", ctypes.c_float * 3),  # 3*4 bytes
        ("fCameraFront", ctypes.c_float * 3),     # 3*4 bytes
        ("fCameraTop", ctypes.c_float * 3),       # 3*4 bytes
        ("identity", ctypes.c_wchar * 256),       # 512 bytes
        ("context_len", ctypes.c_uint32),         # 4 bytes
        # ("context", ctypes.c_ubyte * 256),      # 256 bytes, see below
        # ("description", ctypes.c_wchar * 2048), # 4096 bytes, always empty
    ]


class Context(ctypes.Structure):
    _fields_ = [
        ("serverAddress", ctypes.c_ubyte * 28),   # 28 bytes
        ("mapId", ctypes.c_uint32),               # 4 bytes
        ("mapType", ctypes.c_uint32),             # 4 bytes
        ("shardId", ctypes.c_uint32),             # 4 bytes
        ("instance", ctypes.c_uint32),            # 4 bytes
        ("buildId", ctypes.c_uint32),             # 4 bytes
        ("uiState", ctypes.c_uint32),             # 4 bytes
        ("compassWidth", ctypes.c_uint16),        # 2 bytes
        ("compassHeight", ctypes.c_uint16),       # 2 bytes
        ("compassRotation", ctypes.c_float),      # 4 bytes
        ("playerX", ctypes.c_float),              # 4 bytes
        ("playerY", ctypes.c_float),              # 4 bytes
        ("mapCenterX", ctypes.c_float),           # 4 bytes
        ("mapCenterY", ctypes.c_float),           # 4 bytes
        ("mapScale", ctypes.c_float),             # 4 bytes
        ("processId", ctypes.c_uint32),           # 4 bytes
        ("mountIndex", ctypes.c_uint8),           # 1 byte
    ]


class MumbleLink:
    data = Link
    context = Context
    
    def __init__(self):
        self.size_link = ctypes.sizeof(Link)
        self.size_context = ctypes.sizeof(Context)
        size_discarded = 256 - self.size_context + 4096 # empty areas of context and description
        
        # GW2 won't start sending data if memfile isn't big enough so we have to add discarded bits too
        memfile_length = self.size_link + self.size_context + size_discarded
        
        self.memfile = mmap.mmap(fileno=-1, length=memfile_length, tagname="MumbleLink")
    
    def read(self):
        self.memfile.seek(0)
        
        self.data = self.unpack(Link, self.memfile.read(self.size_link))
        self.context = self.unpack(Context, self.memfile.read(self.size_context))
    
    def close(self):
        self.memfile.close()
    
    @staticmethod
    def unpack(ctype, buf):
        cstring = ctypes.create_string_buffer(buf)
        ctype_instance = ctypes.cast(ctypes.pointer(cstring), ctypes.POINTER(ctype)).contents
        return ctype_instance

def format_polygon(mid, name, lst):
    map = "MapId: {}\n".format(mid)
    snip = "<==========================>"
    out = "{{\n\t\"Name\":\"{}\",\n\t\"Area\": {{\n\t\t\"AreaType\": \"polygon\",\n\t\t\"Polygon\": {}\n\t}}\n}},".format(name,lst)
    print(map+snip+"\n"+out+"\n"+snip)

def format_circle(mid, name, point, radius):
    map = "MapId: {}\n".format(mid)
    snip = "<==========================>"
    out = "{{\n\t\"Name\":\"{}\",\n\t\"Area\": {{\n\t\t\"AreaType\": \"circle\",\n\t\t\"Center\": {},\n\t\t\"Radius\": {}\n\t}}\n}},".format(name,list(point),radius)
    print(map+snip+"\n"+out+"\n"+snip)

def add_tup(a,b):
    return (a[0]+b[0],a[1]+b[1])

def sub_tup(a,b):
    return (a[0]-b[0],a[1]-b[1])

def div_tup(a,b):
    return (a[0]/b,a[1]/b)

def length(tup):
    return math.sqrt(tup[0] ** 2 + tup[1] ** 2)

def normalize(tup):
    a = math.sqrt(tup[0] ** 2 + tup[1] ** 2)
    return div_tup(tup,a)

def marker_handler(number):
    global LINE_MARKER
    global MARKER_MAP
    LINE_MARKER[number] = CURRENT_POS
    MARKER_MAP = CURRENT_MAP
    print(f"Pos {number+1}: {CURRENT_POS} Map: {MARKER_MAP}")

def make_line():
    global LINE_MARKER
    global MARKER_MAP
    if LINE_MARKER[0] != None and LINE_MARKER[1] != None and not LINE_MARKER[0]==LINE_MARKER[1]:
        mid=div_tup(add_tup(LINE_MARKER[0],LINE_MARKER[1]),2)
        line=normalize(sub_tup(LINE_MARKER[0],mid))
        direction1 = (-line[1],line[0])
        direction2 = (line[1],-line[0])
        markers = [list(add_tup(LINE_MARKER[0],direction1)),
                   list(add_tup(LINE_MARKER[0],direction2)),
                   list(add_tup(LINE_MARKER[1],direction2)),
                   list(add_tup(LINE_MARKER[1],direction1))]
        print(MARKER_MAP)
        format_polygon(MARKER_MAP,"Line Marker",markers)
        LINE_MARKER = [None, None]

def make_area():
    format_circle(CURRENT_MAP, "Circle", CURRENT_POS,5)

def make_diameter():
    global LINE_MARKER
    global MARKER_MAP
    if LINE_MARKER[0] != None and LINE_MARKER[1] != None and not LINE_MARKER[0]==LINE_MARKER[1]:
        mid=div_tup(add_tup(LINE_MARKER[0],LINE_MARKER[1]),2)
        radius=length(sub_tup(LINE_MARKER[0],mid))
        format_circle(CURRENT_MAP, "Circle", CURRENT_POS,int(radius))
        LINE_MARKER = [None, None]

keyboard.add_hotkey('alt+1', marker_handler, args=(0,))
keyboard.add_hotkey('alt+2', marker_handler, args=(1,))
keyboard.add_hotkey('alt+l', make_line)
keyboard.add_hotkey('alt+c', make_area)
keyboard.add_hotkey('alt+d', make_diameter)


def main():
    ml = MumbleLink()
    
    # Loop until data could be read.
    ml.read()
    while not ml.data.uiTick:
        time.sleep(1)
        ml.read()

    # do stuff ...
    global CURRENT_POS
    global CURRENT_MAP
    while True:
        CURRENT_POS = (ml.data.fAvatarPosition[0],ml.data.fAvatarPosition[2])
        CURRENT_MAP = ml.context.mapId
        time.sleep(0.1)
        ml.read()
    ml.close()


if __name__ == "__main__":
    print("Focus this window when pressing keys or open as admit for global hotkeys.\nSet Markers using Alt+1 / Alt+2\nGet a line between points with Alt+l\nMark a circle at your position with Alt+c\nMark a circle where Points give the diameter with Alt+d")
    main()

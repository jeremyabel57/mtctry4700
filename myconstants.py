SEP = "|"

# AutoIt source: Opt("GUIOnEventMode", 1) enables GUI OnEvent Mode globally.

COLOR_AQUA = 0x00FFFF
COLOR_BLACK = 0x000000
COLOR_BLUE = 0x0000FF
COLOR_CREAM = 0xFFFBF0
COLOR_FUCHSIA = 0xFF00FF
COLOR_GRAY = 0x808080
COLOR_GREEN = 0x008000
COLOR_LIME = 0x00FF00
COLOR_MAROON = 0x8B1C62
COLOR_MEDBLUE = 0x0002C4
COLOR_MEDGRAY = 0xA0A0A4
COLOR_MONEYGREEN = 0xC0DCC0
COLOR_NAVY = 0x000080
COLOR_OLIVE = 0x808000
COLOR_PURPLE = 0x800080
COLOR_RED = 0xFF0000
COLOR_SILVER = 0xC0C0C0
COLOR_SKYBLUE = 0xA6CAF0
COLOR_TEAL = 0x008080
COLOR_WHITE = 0xFFFFFF
COLOR_YELLOW = 0xFFFF00

CLR_NONE = 0xFFFFFFFF
CLR_DEFAULT = 0xFF000000
CLR_AQUA = 0xFFFF00
CLR_BLACK = 0x000000
CLR_BLUE = 0xFF0000
CLR_CREAM = 0xF0FBFF
CLR_FUCHSIA = 0xFF00FF
CLR_GRAY = 0x808080
CLR_GREEN = 0x008000
CLR_LIME = 0x00FF00
CLR_MAROON = 0x621C8B
CLR_MEDBLUE = 0xC40200
CLR_MEDGRAY = 0xA4A0A0
CLR_MONEYGREEN = 0xC0DCC0
CLR_NAVY = 0x800000
CLR_OLIVE = 0x008080
CLR_PURPLE = 0x800080
CLR_RED = 0x0000FF
CLR_SILVER = 0xC0C0C0
CLR_SKYBLUE = 0xF0CAA6
CLR_TEAL = 0x808000
CLR_WHITE = 0xFFFFFF
CLR_YELLOW = 0x00FFFF

CC_ANYCOLOR = 0x0100
CC_FULLOPEN = 0x0002
CC_RGBINIT = 0x0001


# AutoIt source comments (Python returns a Unicode character directly):
# Function:    ChrW32
# Description: Converts a 32-bit Unicode Code Point into a valid UTF-16 Surrogate Pair string
# Parameter:   $iCodePoint - The 32-bit integer or hex value (e.g., 0x1F4BE)
# Characters inside the Basic Multilingual Plane (0x0000 to 0xFFFF) fit inside a single ChrW
# 1. Shift the code point down into the surrogate working plane
# 2. Apply bitwise shifts or standard division/modulo operators
# 3. Concatenate the two 16-bit segments together into a single string stream
def ChrW32(code_point):
	if not isinstance(code_point, int) or not 0 <= code_point <= 0x10FFFF or 0xD800 <= code_point <= 0xDFFF:
		raise ValueError("Invalid Unicode code point")
	return chr(code_point)


# Icon characters
ICON_CFG = "\ue115"  # ChrW(0x2699); configuration sprocket icon
ICON_STILL_CAMERA2 = "\U0001f4f7"  # screenshot still camera icon
ICON_STILL_CAMERA = "\ue114"  # screenshot still camera icon
ICON_SCREENSHOT = ICON_STILL_CAMERA  # still camera icon
ICON_REFRESH2 = "\u27f3"  # 0x21BB; refresh icon - circle arrow
ICON_REFRESH = "\ue117"  # refresh icon - circle arrow
ICON_POWERBTN = "\u23fb"  # power button
ICON_DEGREE = "\u00b0"  # degree superscript symbol
ICON_DEGREEC = ICON_DEGREE + "C"  # 0x2103; temperature in Celsius
ICON_DEGREEF = ICON_DEGREE + "F"  # 0x2104; temperature in Fahrenheit
ICON_SEARCH = "\ue11a"  # ChrW(0x2315); search magnifying glass
ICON_SEARCH3 = "\u2315"  # search magnifying glass
ICON_SEARCH2 = "\U0001f50d\ufe0e"  # ChrW(0xD83D) & ChrW(0xDD0D)
ICON_GLASS = "\U0001f50d"
ICON_MENU2 = "\u2630"  # parallel horizontal stripes menu button
ICON_MENU1 = "\ue169"  # parallel horizontal stripes menu button
ICON_NET = "\U0001f5a7"  # computers on a network icon
ICON_TABS = "\U0001f5c2"  # 0x29C9, 0x2EB2; tabs icon
ICON_BOOK = "\U0001f56e"  # book icon
ICON_FLOPPY = "\ue105"  # floppy disk icon
ICON_FLOPPY2 = "\U0001f4be"  # ChrW32(0x1F4BE); floppy disk icon
ICON_FOLDER1 = "\U0001f4c1"  # ChrW32(0x1F4C1); folder icon
ICON_FOLDER2 = "\U0001f4c2"  # folder icon
ICON_FOLDERL = "\ue1c1"  # folder icon with tab on the left
ICON_FOLDERR = "\ue188"  # folder icon with tab on the right
ICON_SAVE = ICON_FLOPPY  # floppy disk icon to represent save
ICON_OPEN = ICON_FOLDERL  # folder icon to represent open
ICON_CHECK1 = "\ue10b"  # check
ICON_CHECK2 = "\u2713"  # check
ICON_CHECK2B = "\u2714"  # check bold
ICON_CHECK = ICON_CHECK2  # check
ICON_INFO3 = "\ue2c0"  # information icon
ICON_INFO1 = "\u2139"  # information icon
ICON_INFO2 = "\U0001f6c8"  # information icon
ICON_INFO = ICON_INFO3  # select information icon

ICON_NWARROW1 = "\u2196"  # arrow pointing NW, up left
ICON_NWARROW2 = "\U0001f874"  # arrow pointing NW, up left
ICON_NEARROW1 = "\u2197"  # arrow pointing NE, up right
ICON_NEARROW2 = "\U0001f875"  # arrow pointing NE, up right
ICON_SEARROW1 = "\u2198"  # arrow pointing SE, down right
ICON_SEARROW2 = "\U0001f876"  # arrow pointing SE, down right
ICON_SWARROW1 = "\u2199"  # arrow pointing SW, down left
ICON_SWARROW2 = "\U0001f877"  # arrow pointing SW, down left
ICON_NARROW1 = "\u2191"  # arrow pointing N, up
ICON_NARROW2 = "\U0001f851"  # arrow pointing N, up
ICON_WARROW1 = "\u2192"  # arrow pointing W, left (source description; value points right)
ICON_WARROW2 = "\U0001f850"  # arrow pointing W, left
ICON_EARROW1 = "\u2194"  # arrow pointing E, right (source description; value points left and right)
ICON_EARROW2 = "\U0001f852"  # arrow pointing E, right
ICON_SARROW1 = "\u2195"  # arrow pointing S, down (source description; value points up and down)
ICON_SARROW2 = "\U0001f853"  # arrow pointing S, down

ICON_NTRI = "\u23f6"  # triangle pointing up
ICON_STRI = "\u23f7"  # triangle pointing down
ICON_WTRI = "\u23f4"  # triangle pointing left
ICON_ETRI = "\u23f5"  # triangle pointing right
ICON_UPTRI = "\u23f6"  # triangle pointing up
ICON_DNTRI = "\u23f7"  # triangle pointing down
ICON_LTRI = "\u23f4"  # triangle pointing left
ICON_RTRI = "\u23f5"  # triangle pointing right
ICON_BOX = "\u23f9"  # stop box
ICON_DOT = "\u23fa"  # record circle/dot
ICON_DVB = "\u23f8"  # double vertical pause bars
ICON_PLAY = "\ue102"  # play triangle
ICON_PLAY1 = "\u23f5"  # play triangle
ICON_PLAY2 = "\u25b6"  # play triangle
ICON_PLAYR = "\u23f4"  # reverse play triangle
ICON_PLAYR2 = "\u25c0"  # reverse play triangle
ICON_PAUSE = "\ue103"  # pause double vertical bar
ICON_PAUSE2 = "\u23f8"  # pause double vertical bar
ICON_PLAYPAUSE = "\u23ef"  # play/pause icon
ICON_STOP = "\ue15b"  # stop square
ICON_STOP2 = "\u23f9"  # stop square
ICON_REC = "\u23fa"  # record dot
ICON_FASTFWD = "\u23e9"  # fast forward
ICON_REWIND = "\u23ea"  # rewind
ICON_VBAR = "\u2759"  # 0x23FD; signle vertical bar
ICON_NEXT = "\ue101"  # next
ICON_NEXT1 = ICON_RTRI + ICON_VBAR  # next step
ICON_NEXT2 = "\u23ed"  # next track/step
ICON_PREV = "\ue100"  # previous
ICON_PREV1 = ICON_VBAR + ICON_LTRI  # previous step
ICON_PREV2 = "\u23ee"  # previous track/step
ICON_EJECT = "\u23cf"  # eject symbol
ICON_STEPF = "\u21e5"  # step forward
ICON_STEPB = "\u21e4"  # step backward
ICON_STEPFB = "\u2b72"  # step forward bold
ICON_STEPBB = "\u2b70"  # step backward bold
ICON_STEPFOVER = "\u21b7"  # step forward over
ICON_STEPBOVER = "\u21b6"  # step backward over
ICON_STEPFOUT = "\u21aa"  # step forward out/return
ICON_STEPBOUT = "\u21a9"  # step backward out
ICON_STEPFINTO = "\u21a3"  # step forward info
ICON_STEPBINTO = "\u21a2"  # step back into

COLOR_NEUTRAL = 0xFDFDFD  # neutral or default background color
COLOR_GRAY2 = 0xFDFDFD  # default button and gui background color
# COLOR_RED = 0xFF0000
COLOR_GREEN2 = 0x00FF00  # total green
# COLOR_BLUE = 0x0000FF
# COLOR_YELLOW = 0xFFFF00
COLOR_PURPLE2 = 0xFF00FF  # total purple
# COLOR_BLACK = 0x000000
# COLOR_WHITE = 0xFFFFFF
# COLOR_AZURE = 0x0080FF
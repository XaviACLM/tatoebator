from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QStyle


class Colors:
    std_bg = QColor(249, 249, 249)
    light_emph_bg = QColor(230, 230, 230)
    # for subwidget backgrounds
    emph_bg = QColor(220, 220, 220)

    # for highlights/logos
    tatoebator_blue = QColor(000, 50, 170)

    # for buttons the gui wants you to click
    highlight_blue = QColor(100, 150, 255)

    # no real need to be here, but to avoid ambiguity
    transparent = QColor(0, 0, 0, 0)

    # for use only as text color
    warning_red = QColor(200, 0, 0)

    # for shadow graphics
    shadow = QColor(0, 0, 0)


class SpecialColors:
    # not for general use, only some specific gui elements

    # for selected words in the word displays
    white = QColor(255, 255, 255)
    black = QColor(0, 0, 0)

    #for cell highlighting in the word table
    extra_light_grey = QColor(240, 240, 240)
    dark_grey = QColor(220, 220, 220)
    light_red = QColor(255, 230, 230)
    light_green = QColor(220, 255, 220)


class Pixmaps:
    tick = QStyle.StandardPixmap.SP_DialogApplyButton
    cross = QStyle.StandardPixmap.SP_DialogCancelButton
    q_mark = QStyle.StandardPixmap.SP_TitleBarContextHelpButton
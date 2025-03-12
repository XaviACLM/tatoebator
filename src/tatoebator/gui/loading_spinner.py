import itertools
import math
import random

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget
from time import time as get_time

# this code slightly theseus-shipped but very much built off of the spinner by theycallmek et al:
# https://github.com/theycallmek/QtWaitingSpinner-PySide6

class XavoSpinner(QWidget):
    def __init__(self,
                 parent: QWidget,
                 center_on_parent: bool = True,
                 disable_parent_when_spinning: bool = False,
                 radius: int = 20,
                 color: QColor = QColor(0,50,170),
                 phase_time = 1.5):
        super().__init__(parent)

        self.parent = parent
        self.radius = radius
        self.color = color
        self.phase_time = phase_time
        self.center_on_parent = center_on_parent
        self.disable_parent_when_spinning = disable_parent_when_spinning

        self.dot_radius = self.radius//4

        self.spinning_plan = SpinningPlan(2, 6, math.pi/2, -math.pi/2, 0, 0)

        self._timer: QTimer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.setInterval(int(1000*self.phase_time/100))  # ms

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        size = 2 * int(self.dot_radius+self.radius*(1+self.spinning_plan.derangement_rad))
        self.setFixedSize(size, size)

        self.hide()


    def start(self):
        self._timer.start()
        self.show()
        if self.disable_parent_when_spinning:
            self.parentWidget().setEnabled(False)

    def stop(self):
        self._timer.stop()
        self.hide()
        if self.disable_parent_when_spinning:
            self.parentWidget().setEnabled(True)

    def _update_spinning_plan(self, time: float):
        if self.spinning_plan.is_finished(time):
            n_orig = self.spinning_plan.n_dest
            phase_orig = self.spinning_plan.phase_dest
            while True:
                n_dest = random.choice((3,5,7))
                #n_dest = random.randint(2,7)
                if math.gcd(n_orig, n_dest) == 1: break
            phase_dest = (phase_orig+math.pi)%(2*math.pi)
            self.spinning_plan = SpinningPlan(n_orig, n_dest, phase_orig, phase_dest, time, self.phase_time)

    def paintEvent(self, _: QPaintEvent) -> None:
        time = get_time()
        self._update_spinning_plan(time)

        if self.parentWidget() and self.center_on_parent:
            self.move(
                (self.parentWidget().width() - self.width()) // 2,
                (self.parentWidget().height() - self.height()) // 2,
            )

        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(Qt.PenStyle.NoPen)
        for ox, oy, heading, speed in self.spinning_plan.get_positions_at(time):
            painter.save()
            painter.translate((1 + ox) * self.radius + self.dot_radius,
                              (1 + oy) * self.radius + self.dot_radius)
            painter.rotate(360*heading/(2*math.pi))

            painter.setBrush(self.color)

            axis = int(self.dot_radius/max(1,20*min(speed,0.10)))
            painter.drawEllipse(-self.dot_radius//2, -axis//2, self.dot_radius, axis)
            painter.restore()


class SpinningPlan:
    def __init__(self,
                 n_orig: int,
                 n_dest: int,
                 phase_orig: float,
                 phase_dest: float,
                 start_time: float,
                 total_time: float):
        self.n_orig = n_orig
        self.n_dest = n_dest
        self.phase_orig = phase_orig
        self.phase_dest = phase_dest
        self.start_time = start_time
        self.total_time = total_time
        self.old_positions = itertools.repeat(None)

        self.derangement_rad = 0.1
        self.derangements = self._generate_derangements()
        self.backwards = self._generate_backwards()

    def _generate_derangements(self):
        rad = self.derangement_rad
        derangements = []
        for _ in range(self.n_orig*self.n_dest):
            alpha = random.uniform(0, 2*math.pi)
            x, y = rad*math.cos(alpha), rad*math.sin(alpha)
            derangements.append((x, y))
        return derangements

    def _generate_backwards(self):
        if random.randint(1,100) < 100:
            return itertools.repeat(False)
        return [random.choice((True, False)) for _ in range(self.n_orig*self.n_dest)]

    def get_positions_at(self, time: float):
        t = (time-self.start_time)/self.total_time
        if t>1: raise ValueError('time has to be before start_time+total_time')

        positions = []
        old_positions = iter(self.old_positions)

        f = t>0 and 1/(1+((1/t)-1)**4)
        f_ = math.sin(t*math.pi)**2
        f_ = f_**(3)

        for (alpha_orig, alpha_dest), (derangement_x, derangement_y), backwards \
                in zip(itertools.product([self.phase_orig + i/self.n_orig*2*math.pi for i in range(self.n_orig)],
                                         [self.phase_dest + i/self.n_dest*2*math.pi for i in range(self.n_dest)]),
                       self.derangements,
                       self.backwards):
            alpha_d = (alpha_dest - alpha_orig) % (2*math.pi)
            if backwards:
                alpha_d -= 2*math.pi
                derangement_x = derangement_x*0.3 - 0.3
            alpha_now = alpha_orig + f*alpha_d
            x, y = 1+f_*derangement_x, f_*derangement_y
            s, c = math.cos(alpha_now), math.sin(alpha_now)
            x, y = s*x - c*y, c*x + s*y
            old_position = next(old_positions)
            if old_position is None:
                positions.append((x,y,0,0))
            else:
                old_x, old_y, _, _ = old_position
                dx, dy = x-old_x, y-old_y
                heading = math.atan2(dy, dx)
                v = math.sqrt(dx*dx + dy*dy)
                positions.append((x, y, heading, v))

        self.old_positions = positions
        return positions

    def is_finished(self, time: float):
        return time-self.start_time > self.total_time

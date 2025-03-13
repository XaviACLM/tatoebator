import itertools
import math
import os
import random
from enum import Enum
from functools import cached_property
from time import time as get_time
from typing import Protocol, Optional, Callable, Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

from ..constants import PATH_TO_OTHER_DATA


# this code slightly theseus-shipped but very much built off of the spinner by theycallmek et al:
# https://github.com/theycallmek/QtWaitingSpinner-PySide6

class XavoSpinner(QWidget):
    def __init__(self,
                 parent: QWidget,
                 center_on_parent: bool = True,
                 disable_parent_when_spinning: bool = False,
                 radius: int = 20,
                 color: QColor = QColor(0, 50, 170),
                 phase_time=1.5):
        super().__init__(parent)

        self.parent = parent
        self.radius = radius
        self.color = color
        self.phase_time = phase_time
        self.center_on_parent = center_on_parent
        self.disable_parent_when_spinning = disable_parent_when_spinning

        self._load_polygon_transitions()

        self.dot_radius = self.radius // 4
        self._queued_ending_animation = False
        self._playing_ending_animation = False
        self._ending_callback = None
        self.derangement_rad = 0.1

        self._timer: QTimer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.setInterval(int(1000 * self.phase_time / 100))  # ms

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        size = 2 * int(self.dot_radius + self.radius * (1 + self.derangement_rad))
        self.setFixedSize(size, size)

        self.hide()

    def start(self):
        self._timer.start()
        self.show()
        if self.disable_parent_when_spinning:
            self.parentWidget().setEnabled(False)
        self.spinning_plan = NormalSpin(3, 5, math.pi / 2, -math.pi / 2, get_time(), self.phase_time,
                                        mode=SpinnerMode.START,
                                        derangement_rad=self.derangement_rad,
                                        backwards=False)

    def stop(self):
        self._timer.stop()
        self.hide()
        if self.disable_parent_when_spinning:
            self.parentWidget().setEnabled(True)
        if self._ending_callback is not None:
            c = self._ending_callback
            self._ending_callback = None
            c()

    def stop_with_animation(self, callback: Optional[Callable[..., Any]] = None):
        self._queued_ending_animation = True
        self._ending_callback = callback

    def _load_polygon_transitions(self):
        filepath = os.path.join(PATH_TO_OTHER_DATA, 'polygon_transitions.txt')
        polygons = []
        transitions = []
        with open(filepath, "r") as f:
            for line in f:
                if not line.startswith("#"):
                    n = int(line[:-1])
                    break
            for i in range(n):
                line = next(f)
                n_vertices, askew = line[:-1].split('\t')
                n_vertices = int(n_vertices)
                askew = askew == 'True'
                polygons.append((n_vertices, askew))
            for i in range(n):
                line = next(f)
                probabilities = line[:-1].split('\t')
                probabilities = list(map(float, probabilities))
                transitions.append(probabilities)
        self._polygons = polygons
        self._transitions = transitions

    def _update_spinning_state(self, time: float):
        if self._queued_ending_animation:
            self._queued_ending_animation = False
            self._playing_ending_animation = True
            mode = SpinnerMode.END
        else:
            mode = SpinnerMode.NORMAL

        n_orig = self.spinning_plan.n_dest
        phase_orig = self.spinning_plan.phase_dest

        askew_orig = abs(phase_orig - math.pi / 2) > 1e-5
        i_orig = self._polygons.index((n_orig, askew_orig))
        transitions = self._transitions[i_orig]
        i_dest, = random.choices(range(len(self._polygons)), weights=transitions)

        n_dest, askew_dest = self._polygons[i_dest]
        phase_dest = (2 * math.pi) / (2 * n_dest) if askew_dest else 0
        phase_dest += math.pi / 2

        if random.randint(1,200)>1 or self._playing_ending_animation:
            backwards = random.randint(1, 20) == 1
            self.spinning_plan = NormalSpin(n_orig, n_dest, phase_orig, phase_dest, time, self.phase_time,
                                            mode=mode,
                                            derangement_rad=self.derangement_rad,
                                            backwards=backwards)
        else:
            #oops!
            self.spinning_plan = BlobbySpin(n_orig, n_dest, phase_orig, phase_dest, time, self.phase_time*2, 50)

    def paintEvent(self, _: QPaintEvent) -> None:
        time = get_time()
        if self.spinning_plan.is_finished(time):
            if self._playing_ending_animation:
                self._playing_ending_animation = False
                return self.stop()
                return
            self._update_spinning_state(time)

        if self.parentWidget() and self.center_on_parent:
            self.move(
                (self.parentWidget().width() - self.width()) // 2,
                (self.parentWidget().height() - self.height()) // 2,
            )

        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(Qt.PenStyle.NoPen)
        for ox, oy, heading, speed, size_modifier in self.spinning_plan.get_positions_at(time):
            painter.save()
            painter.translate((1 + ox) * self.radius + self.dot_radius,
                              (1 + oy) * self.radius + self.dot_radius)
            painter.rotate(360 * heading / (2 * math.pi))

            painter.setBrush(self.color)

            axis = int(self.dot_radius / max(1, 20 * min(speed, 0.10)))
            major = int(size_modifier*self.dot_radius)
            minor = int(size_modifier*axis)
            painter.drawEllipse(-major // 2, -minor // 2, major, minor)
            painter.restore()


class SpinnerMode(Enum):
    NORMAL = 0
    START = 1
    END = -1


class SpinningProtocol(Protocol):
    def get_positions_at(self, time: float):
        ...

    def is_finished(self, time: float):
        ...


class NormalSpin(SpinningProtocol):
    def __init__(self,
                 n_orig: int,
                 n_dest: int,
                 phase_orig: float,
                 phase_dest: float,
                 start_time: float,
                 total_time: float,
                 mode: SpinnerMode = SpinnerMode.NORMAL,
                 derangement_rad=0.1,
                 backwards=False):
        self.n_orig = n_orig
        self.n_dest = n_dest
        self.phase_orig = phase_orig
        self.phase_dest = phase_dest
        self.start_time = start_time
        self.total_time = total_time
        self.derangement_rad = derangement_rad
        self.mode = mode

        self.old_positions = itertools.repeat(None)

        self.derangements = self._generate_derangements()
        if backwards:
            self.backwards = self._generate_backwards()
        else:
            self.backwards = itertools.repeat(False)

    def _generate_derangements(self):
        rad = self.derangement_rad
        derangements = []
        for _ in range(self.n_orig * self.n_dest):
            alpha = random.uniform(0, 2 * math.pi)
            x, y = rad * math.cos(alpha), rad * math.sin(alpha)
            derangements.append((x, y))
        return derangements

    def _generate_backwards(self):
        return [random.choice((True, False)) for _ in range(self.n_orig * self.n_dest)]

    def get_positions_at(self, time: float):
        t = (time - self.start_time) / self.total_time
        if t > 1: raise ValueError('time has to be before start_time+total_time')

        positions = []
        old_positions = iter(self.old_positions)

        f = t > 0 and 1 / (1 + ((1 / t) - 1) ** 4)
        f_ = math.sin(t * math.pi) ** 2
        f_ = f_ ** (3)

        for (alpha_orig, alpha_dest), (derangement_x, derangement_y), backwards \
                in zip(itertools.product([self.phase_orig + i / self.n_orig * 2 * math.pi for i in range(self.n_orig)],
                                         [self.phase_dest + i / self.n_dest * 2 * math.pi for i in range(self.n_dest)]),
                       self.derangements,
                       self.backwards):
            alpha_d = (alpha_dest - alpha_orig) % (2 * math.pi)
            if backwards:
                alpha_d -= 2 * math.pi
                derangement_x = derangement_x * 0.3 - 0.3
            alpha_now = alpha_orig + f * alpha_d
            x, y = 1 + f_ * derangement_x, f_ * derangement_y
            s, c = math.cos(alpha_now), math.sin(alpha_now)
            x, y = s * x - c * y, c * x + s * y
            if self.mode is not SpinnerMode.NORMAL:
                if self.mode is SpinnerMode.START:
                    x, y = x * f, y * f
                else:
                    x, y = x * (1 - f), y * (1 - f)
            old_position = next(old_positions)
            if old_position is None:
                positions.append((x, y, 0, 0, 1))
            else:
                old_x, old_y, _, _, _ = old_position
                dx, dy = x - old_x, y - old_y
                heading = math.atan2(dy, dx)
                v = math.sqrt(dx * dx + dy * dy)
                positions.append((x, y, heading, v, 1))

        self.old_positions = positions
        return positions

    def is_finished(self, time: float):
        return time - self.start_time > self.total_time


class BlobbySpin:

    # rather wasteful - this would be acceptable w numpy, but i don't want to introduce the massive dependency
    # can't help myself from this, though

    # this is quite bad code. just a fun easter egg, though, so it gets to stay

    def __init__(self,
                 n_orig: int,
                 n_dest: int,
                 phase_orig: float,
                 phase_dest: float,
                 start_time: float,
                 total_time: float,
                 amt_dots: int,
                 backwards=False):
        self.n_orig = n_orig
        self.n_dest = n_dest
        self.phase_orig = phase_orig
        self.phase_dest = phase_dest
        self.start_time = start_time
        self.total_time = total_time
        self.amt_dots = amt_dots

        self.derangements = self._generate_derangements()
        self.old_positions = self._get_starting_positions()

        self.backwards = backwards

        self.last_update_time = None

    def is_finished(self, time: float):
        return time - self.start_time > self.total_time

    def _generate_derangements(self):
        rad = 0.001
        derangements = []
        for _ in range(self.amt_dots):
            alpha = random.uniform(0, 2 * math.pi)
            x, y = rad * math.cos(alpha), rad * math.sin(alpha)
            derangements.append((x, y))
        return derangements

    def _get_starting_positions(self):
        positions = []
        for _, i, (dr_x, dr_y) in zip(range(self.amt_dots), itertools.cycle(range(self.n_orig)), self.derangements):
            phase = self.phase_orig + i / self.n_orig * 2 * math.pi
            c, s = math.cos(phase), math.sin(phase)
            x, y = c+dr_x, s+dr_y
            positions.append((x, y, 0, 0, 1))
        return positions

    @cached_property
    def _final_nodes(self):
        positions = []
        for i in range(self.n_dest):
            phase = self.phase_dest + i / self.n_dest * 2 * math.pi
            x, y = math.cos(phase), math.sin(phase)
            positions.append((x, y))
        return positions

    def get_positions_at(self, time: float):
        t = (time - self.start_time) / self.total_time
        if t > 1: raise ValueError('time has to be before start_time+total_time')

        if self.last_update_time is None:
            time_step = 0
        else:
            time_step = time-self.last_update_time
        self.last_update_time = time

        old_positions = [(x,y) for x,y,_,_,_ in self.old_positions]

        # forces acting on these particles:
        # repulsion from each other (stronger towards the center)
        # repulsion from edges of circle
        # slight clockwise force
        # attraction towards their (closest?) destination, at the end

        # let's not really do forces, lets just say they follow the flux... etc etc, ykwim

        w1 = t > 0 and 1 / (1 + ((1 / (0.4+t)) - 1)**4)
        dot_dot_repulsion_intensity = w1*0.01*(1-min(1,(t+0.5)**2))
        edge_repulsion_intensity = w1*1
        rotation_intensity = 2*(t-1)**2
        final_pull_intensity = min(1,(t+0.15)**2)


        modulus = [math.sqrt(x*x+y*y) for x,y in old_positions]
        movement = [[0,0] for _ in range(self.amt_dots)]

        middle_factors = [1-m*m for m in modulus]
        for i in range(self.amt_dots):
            mi = 1-middle_factors[i]
            x1, y1 = old_positions[i]
            for j in range(i+1, self.amt_dots):
                mj = 1-middle_factors[i]
                x2, y2 = old_positions[j]
                dx, dy = x1 - x2, y1 - y2
                d = dx*dx + dy*dy
                d = max(d,0.01)
                dd = d*d  # for force this should be d*d*d (first d cancels out modulus), but we're doing the integral
                fx, fy = dx/dd, dy/dd
                fx *= dot_dot_repulsion_intensity
                fy *= dot_dot_repulsion_intensity
                movement[i][0] += fx*mi
                movement[i][1] += fy*mi
                movement[j][0] -= fx*mj
                movement[j][1] -= fy*mj

        for i,(m,(x,y)) in enumerate(zip(modulus, old_positions)):
            fm = m if m>1 else m*m
            fm *= edge_repulsion_intensity
            fx = x*fm
            fy = y*fm
            movement[i][0] -= fx
            movement[i][1] -= fy

        for i,(m,(x,y)) in enumerate(zip(modulus, old_positions)):
            fm = 3*m
            fm *= rotation_intensity
            fx = y*fm
            fy = -x*fm
            movement[i][0] -= fx
            movement[i][1] -= fy

        final_nodes = self._final_nodes
        targets = []
        for i,(x,y) in enumerate(old_positions):
            min_d = float('inf')
            for final_x, final_y in final_nodes:
                dx = x-final_x
                dy = y-final_y
                c_d = dx*dx+dy*dy
                if c_d<min_d:
                    min_d = c_d
                    min_dx = dx
                    min_dy = dy
            targets.append((min_d, min_dx, min_dy))
            min_d = max(min_d, 0.01)
            dx = min_dx/min_d*final_pull_intensity
            dy = min_dy/min_d*final_pull_intensity
            movement[i][0] -= dx
            movement[i][1] -= dy


        new_positions = [(x+mx*time_step, y+my*time_step) for (x,y),(mx,my) in zip(old_positions, movement)]

        for i, ((x, y), (old_x, old_y), (td, tdx, tdy)) in enumerate(zip(new_positions, old_positions, targets)):
            dx, dy = x - old_x, y - old_y
            heading = math.atan2(dy, dx)
            v = math.sqrt(dx * dx + dy * dy)
            mod = math.sqrt(x*x+y*y)
            if mod>1.1:
                x/=mod
                y/=mod
                mod = 1.1
            otd = td-2*(1-t)
            if otd>0:
                f = otd/td
                x -= tdx*f
                y -= tdy*f
            new_positions[i] = (x, y, heading, v, 0.5+0.5*mod)
        self.old_positions = new_positions

        return new_positions

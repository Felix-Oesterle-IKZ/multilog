import logging
import time
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QFrame,
    QLineEdit,
    QSplitter,
    QLabel,
    QCheckBox,
    QGroupBox,
    QLineEdit,
)
import pyqtgraph as pg

from .base_classes import ImageWidget
from ..devices.basler_camera import BaslerCamera

logger = logging.getLogger(__name__)
class LineEdit(QLineEdit):
    """Modified of QLineEdit: red color if modified and not saved."""

    def __init__(self, parent=None):
        super(LineEdit, self).__init__(parent)

    def focusInEvent(self, e):
        super(LineEdit, self).focusInEvent(e)
        self.setStyleSheet("color: red")
        self.selectAll()

    def mousePressEvent(self, e):
        self.setStyleSheet("color: red")
        self.selectAll()

class BaslerCameraWidget(ImageWidget):
    def __init__(self, basler_camera: BaslerCamera, parent=None):
        """GUI widget of Basler optical camera.

        Args:
            basler_camera (BaslerCamera): BaslerCamera device including
                configuration information.
        """
        logger.info(f"Setting up BaslerCameraWidget  for device {basler_camera.name}")
        super().__init__(parent)
        self.cam = basler_camera

        # Camera Settings
        self.group_box_plot = QGroupBox("Camera settings")
        self.group_box_plot_layout = QGridLayout()
        self.group_box_plot.setLayout(self.group_box_plot_layout)
        self.parameter_layout.addWidget(self.group_box_plot)
        self.parameter_layout.setAlignment(self.group_box_plot, Qt.AlignTop)

        # Exposure Time
        self.exp = 0
        self.lbl_exp_edit = QLabel("Exposure Time [ms]: ")
        self.lbl_exp_edit.setFont(QFont("Times", 12))
        self.lbl_exp_edit.setAlignment(Qt.AlignRight)
        self.group_box_plot_layout.addWidget(self.lbl_exp_edit, 0, 0, 1, 1)
        self.group_box_plot_layout.setAlignment(self.lbl_exp_edit, Qt.AlignBottom)

        self.edit_exp_edit = LineEdit()
        self.edit_exp_edit.setFixedWidth(90)
        self.edit_exp_edit.setFont(QFont("Times", 14, QFont.Bold))
        self.edit_exp_edit.setText(str(basler_camera.get_exposure_time()))
        #self.edit_exp_edit.setEnabled(False)
        self.group_box_plot_layout.addWidget(self.edit_exp_edit, 0, 1, 1, 1)
        self.group_box_plot_layout.setAlignment(self.edit_exp_edit, Qt.AlignBottom)
        self.edit_exp_edit.editingFinished.connect(self.update_edit_exp)

        # Frame Rate
        self.fps = 0
        self.lbl_fps_edit = QLabel("Framerate [FPS]: ")
        self.lbl_fps_edit.setFont(QFont("Times", 12))
        self.lbl_fps_edit.setAlignment(Qt.AlignRight)
        self.group_box_plot_layout.addWidget(self.lbl_fps_edit, 1, 0, 1, 1)
        self.group_box_plot_layout.setAlignment(self.lbl_fps_edit, Qt.AlignBottom)

        self.edit_fps_edit = LineEdit()
        self.edit_fps_edit.setFixedWidth(90)
        self.edit_fps_edit.setFont(QFont("Times", 14, QFont.Bold))
        self.edit_fps_edit.setText(str(basler_camera.get_frame_rate()))
        #self.edit_fps_edit.setEnabled(False)
        self.group_box_plot_layout.addWidget(self.edit_fps_edit, 1, 1, 1, 1)
        self.group_box_plot_layout.setAlignment(self.edit_fps_edit, Qt.AlignBottom)
        self.edit_fps_edit.editingFinished.connect(self.update_fps)

        # Data Storage Checkbox
        self.lbl_data = QLabel("Enable Datastorage: ")
        self.lbl_data.setFont(QFont("Times", 12))
        self.lbl_data.setAlignment(Qt.AlignRight)
        self.group_box_plot_layout.addWidget(self.lbl_data, 2, 0, 1, 1)
        self.group_box_plot_layout.setAlignment(self.lbl_data, Qt.AlignBottom)

        self.cb_data = QCheckBox()
        self.cb_data.setChecked(True)
        self.cb_data.setFont(QFont("Times", 12))
        self.cb_data.setEnabled(True)
        self.group_box_plot_layout.addWidget(self.cb_data, 2, 1, 1, 1)
        self.group_box_plot_layout.setAlignment(self.cb_data, Qt.AlignBottom)
        self.cb_data.clicked.connect(self.update_cb_data)

    def update_edit_exp(self):
        try: newExp = float(self.edit_exp_edit.text().replace(",", "."))
        except: newExp = self.cam.get_exposure_time()
        self.cam._set_exposure_time(newExp)
        time.sleep(0.1)
        self.edit_exp_edit.setText(str(self.cam.get_exposure_time()))
        self.edit_exp_edit.setStyleSheet("color: black")
        self.edit_exp_edit.clearFocus()

    def update_fps(self):
        try: newFps = float(self.edit_fps_edit.text().replace(",", "."))
        except: newFps = self.cam.get_frame_rate()
        self.cam.set_frame_rate(newFps)
        time.sleep(0.1)
        self.edit_fps_edit.setText(str(self.cam.get_frame_rate()))
        self.edit_fps_edit.setStyleSheet("color: black")
        self.edit_fps_edit.clearFocus()

    def update_cb_data(self):
        if self.cb_data.isChecked():
            self.cam.setEnableDataStorage(True)
        else:
            self.cam.setEnableDataStorage(False)

    def set_initialization_data(self, sampling):
        """Update image with sampling data (used before recording is
        started).

        Args:
            sampling (np.array): image.
        """
        self.set_image(np.swapaxes(sampling, 0, 1))

    def set_measurement_data(self, rel_time, meas_data):
        """Update plot and labels with measurement data (used after
        recording was started).

        Args:
            rel_time (list): relative time of measurement data. Unused.
            meas_data (np.array): image.
        """
        self.set_image(np.swapaxes(meas_data, 0, 1))

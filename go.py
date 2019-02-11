#!/usr/local/bin/python3

from PyQt5 import QtGui, QtCore

import sys
import ui_main
import scipy.signal
import numpy as np
import pyqtgraph
from swhear import SWHear


class PassiveDoppler(QtGui.QMainWindow, ui_main.Ui_MainWindow):
    def __init__(self, parent=None):
        pyqtgraph.setConfigOption('background', 'w')  # before loading widget
        super(PassiveDoppler, self).__init__(parent)

        self.mode_ambient = False
        self.setupUi(self)
        self.btnAmbient.clicked.connect(self.on_click)
        self.btnReset.clicked.connect(self.on_reset)
        self.grFFT.plotItem.showGrid(True, True, 0.7)
        self.grPCM.plotItem.showGrid(True, True, 0.7)
        self.maxFFT = 0
        self.maxPCM = 0
        # self.ear = SWHear(rate=44100, updatesPerSecond=5)
        self.ear = SWHear(rate=4000, updatesPerSecond=10)
        self.ear.signalSamplesUpdate.connect(self.update_sample_count)
        self.ear.stream_start()

    @QtCore.pyqtSlot()
    def on_click(self):
        self.mode_ambient = not self.mode_ambient
        self.ear.ambient_sample_mode = self.mode_ambient

    @QtCore.pyqtSlot()
    def on_reset(self):
        self.mode_ambient = False
        self.ear.reset()

    def acquire_ambient(self):
        pass

    @QtCore.pyqtSlot(int)
    def update_sample_count(self, count):
        print("update_sample_count(): {0:d}".format(count))
        self.lcdSamples.display(count)

    def update(self):
        if self.mode_ambient:
            self.acquire_ambient()

        elif (self.ear.data is not None) and (self.ear.fft is not None):
            pcmMax = np.max(np.abs(self.ear.data))
            if pcmMax > self.maxPCM:
                self.maxPCM = pcmMax
                self.grPCM.plotItem.setRange(yRange=[-pcmMax, pcmMax])
            if np.max(self.ear.fft) > self.maxFFT:
                self.maxFFT = np.max(np.abs(self.ear.fft))
                # self.grFFT.plotItem.setRange(yRange=[0,self.maxFFT])
                self.grFFT.plotItem.setRange(yRange=[0, 1])
            self.pbLevel.setValue(1000 * pcmMax / self.maxPCM)

            # ---- Peak finding in frequency domain -----------------
            peaks, _ = scipy.signal.find_peaks(self.ear.fft, height=0.1*self.maxFFT)
            # ---------------------------------------------------------

            pen = pyqtgraph.mkPen(color='b')
            peak_pen = pyqtgraph.mkPen(color='g')

            self.grPCM.plot(self.ear.datax, self.ear.data, pen=pen, clear=True)
            pen = pyqtgraph.mkPen(color='r')
            self.grFFT.plot(self.ear.fftx, self.ear.fft / self.maxFFT, pen=pen, clear=True)

            # plot peaks
            self.grFFT.plot(self.ear.fftx[peaks], self.ear.fft[peaks]/self.maxFFT, pen=None, symbol='o', clear=False)

        QtCore.QTimer.singleShot(1, self.update)  # QUICKLY repeat


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    form = PassiveDoppler()
    form.show()
    form.update()  # start with something
    app.exec_()
    print("DONE")

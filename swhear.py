"""
this is a stripped down version of the SWHear class.
It's designed to hold only a single audio sample in memory.
check my githib for a more complete version:
    http://github.com/swharden
"""

import pyaudio
import time
import numpy as np
import threading
from PyQt5 import QtCore


def getFFT(data, rate):
    """Given some data and rate, returns FFTfreq and FFT (half)."""
    data = data * np.hamming(len(data))
    fft = np.fft.fft(data)
    fft = np.abs(fft)
    # fft=10*np.log10(fft)
    freq = np.fft.fftfreq(len(fft), 1.0 / rate)
    return freq[:int(len(freq) / 2)], fft[:int(len(fft) / 2)]


class SWHear(QtCore.QObject):
    """
    The SWHear class is provides access to continuously recorded
    (and mathematically processed) microphone data.

    Arguments:

        device - the number of the sound card input to use. Leave blank
        to automatically detect one.

        rate - sample rate to use. Defaults to something supported.

        updatesPerSecond - how fast to record new data. Note that smaller
        numbers allow more data to be accessed and therefore high
        frequencies to be analyzed if using a FFT later
    """
    signalSamplesUpdate = QtCore.pyqtSignal(int)

    def __init__(self, device=None, rate=None, updatesPerSecond=10):
        super(SWHear, self).__init__()
        # Added a signal
        self.__ambient = None
        self.p = pyaudio.PyAudio()
        self.chunk = 4096  # gets replaced automatically
        self.updatesPerSecond = updatesPerSecond
        self.chunksRead = 0
        self.device = device
        self.rate = rate
        self.data = None
        self.datax = None
        self.fft = None
        self.fftx = None
        self.ambient_samples = 0
        self.ambient_sample_mode = False

    def __del__(self):
        self.close()

    def reset(self):
        self.__ambient = None
        self.ambient_samples = 0
        self.ambient_sample_mode = False

    @property
    def ambient_samples(self):
        return self.__ambient_samples

    @ambient_samples.setter
    def ambient_samples(self, samples):
        self.__ambient_samples = samples
        self.signalSamplesUpdate.emit(samples)

    @property
    def ambient_sample_mode(self):
        return self.__isAmbientSampleMode

    @ambient_sample_mode.setter
    def ambient_sample_mode(self, mode):
        self.__isAmbientSampleMode = mode
        # if ambient sampling has just been activated, then reset sample count to zero
        if mode:
            self.ambient_samples = 0
            self.__ambient = None

        else:  # deactivate ambient sampling
            # Calculate the mean ambient spectrum
            if (self.__ambient is not None) and (self.__ambient_samples > 0):
                print("Samples = {0:d}".format(self.__ambient_samples))
                self.__ambient = np.divide(self.__ambient, self.__ambient_samples)

    # SYSTEM TESTS

    def valid_low_rate(self, device):
        """set the rate to the lowest supported audio rate."""
        for testrate in [44100]:
            if self.valid_test(device, testrate):
                return testrate
        print(("SOMETHING'S WRONG! I can't figure out how to use DEV", device))
        return None

    def valid_test(self, device, rate=44100):
        """given a device ID and a rate, return TRUE/False if it's valid."""
        try:
            self.info = self.p.get_device_info_by_index(device)
            if not self.info["maxInputChannels"] > 0:
                return False
            stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                 input_device_index=device, frames_per_buffer=self.chunk,
                                 rate=int(self.info["defaultSampleRate"]), input=True)
            stream.close()
            return True
        except:
            return False

    def valid_input_devices(self):
        """
        See which devices can be opened for microphone input.
        call this when no PyAudio object is loaded.
        """
        mics = []
        for device in range(self.p.get_device_count()):
            if self.valid_test(device):
                mics.append(device)
        if len(mics) == 0:
            print("no microphone devices found!")
        else:
            print(("found %d microphone devices: %s" % (len(mics), mics)))
        return mics

    ### SETUP AND SHUTDOWN

    def initiate(self):
        """run this after changing settings (like rate) before recording"""
        if self.device is None:
            self.device = self.valid_input_devices()[0]  # pick the first one
        if self.rate is None:
            self.rate = self.valid_low_rate(self.device)
        self.chunk = int(self.rate / self.updatesPerSecond)  # hold one tenth of a second in memory
        if not self.valid_test(self.device, self.rate):
            print("guessing a valid microphone device/rate...")
            self.device = self.valid_input_devices()[0]  # pick the first one
            self.rate = self.valid_low_rate(self.device)
        self.datax = np.arange(self.chunk) / float(self.rate)
        msg = 'recording from "%s" ' % self.info["name"]
        msg += '(device %d) ' % self.device
        msg += 'at %d Hz' % self.rate
        print(msg)

    def close(self):
        """gently detach from things."""
        print(" -- sending stream termination command...")
        self.keepRecording = False  # the threads should self-close
        while (self.t.isAlive()):  # wait for all threads to close
            time.sleep(.1)
        self.stream.stop_stream()
        self.p.terminate()

    ### STREAM HANDLING

    def stream_readchunk(self):
        """reads some audio and re-launches itself"""
        try:
            self.data = np.fromstring(self.stream.read(self.chunk), dtype=np.int16)
            self.fftx, self.fft = getFFT(self.data, self.rate)
            if self.__isAmbientSampleMode:
                if self.__ambient is not None:
                    self.__ambient = np.add(self.__ambient, self.fft)
                else:
                    self.__ambient = np.copy(self.fft)
                self.ambient_samples += 1
            elif self.__ambient is not None:
                self.fft = np.subtract(self.fft, self.__ambient)

        except Exception as E:
            print(" -- exception! terminating...")
            print((E, "\n" * 5))
            self.keepRecording = False
        if self.keepRecording:
            self.stream_thread_new()
        else:
            self.stream.close()
            self.p.terminate()
            print(" -- stream STOPPED")
        self.chunksRead += 1

    def stream_thread_new(self):
        self.t = threading.Thread(target=self.stream_readchunk)
        self.t.start()

    def stream_start(self):
        """adds data to self.data until termination signal"""
        self.initiate()
        print(" -- starting stream")
        self.keepRecording = True  # set this to False later to terminate stream
        self.data = None  # will fill up with threaded recording data
        self.fft = None
        self.dataFiltered = None  # same
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                  rate=self.rate, input=True, frames_per_buffer=self.chunk)
        self.stream_thread_new()



if __name__ == "__main__":
    # ear = SWHear(updatesPerSecond=20)  # optionally set sample rate here
    # ear.stream_start()  # goes forever
    lastRead = ear.chunksRead
    while True:
        while lastRead == ear.chunksRead:
            time.sleep(.01)
        print((ear.chunksRead, len(ear.data)))
        lastRead = ear.chunksRead
    print("DONE")

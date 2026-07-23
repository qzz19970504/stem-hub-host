from PySide6 import QtCore, QtSerialPort, QtWidgets
import pyqtgraph
import numpy as np
print('PySide6', QtCore.__version__)
print('pyqtgraph', pyqtgraph.__version__)
print('numpy', np.__version__)
print('QtSerialPort ok:', hasattr(QtSerialPort, 'QSerialPort'))
print('QtWidgets ok:', hasattr(QtWidgets, 'QApplication'))

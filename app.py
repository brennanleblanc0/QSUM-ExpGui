from PyQt6 import QtCore, QtWidgets, uic
import sys

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kargs):
        super(MainWindow, self).__init__(*args, **kargs)
        uic.loadUi("mainwindow.ui", self)

def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    app.exec()

if __name__ == '__main__':
    main()
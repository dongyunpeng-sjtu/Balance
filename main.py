try:
    import sys
    from PyQt5 import QtWidgets
    import os
    from Main_Window import MainWindow

    if __name__ == '__main__':
        os.chdir(os.path.dirname(__file__))
        app = QtWidgets.QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
except Exception as e:
    import os
    import traceback
    
    os.chdir(os.path.dirname(__file__))

    print(str(e))
    print(traceback.print_exc())
    with open('error_log.txt','w') as f:
        f.write(str(e)+'\n')
        traceback.print_exc(file=f)

# import sys
# from PyQt5 import QtWidgets
# import os
# from Main_Window import MainWindow

# if __name__ == '__main__':
#     os.chdir(os.path.dirname(__file__))
#     app = QtWidgets.QApplication(sys.argv)
#     window = MainWindow()
#     window.show()
#     sys.exit(app.exec_())
    
    
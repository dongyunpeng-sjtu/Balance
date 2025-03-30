# # self.all_data=[
# #                {"core_data":ctx,"other_data":{很多键值对（控件上的数据）}}
# #                {"core_data":ctx,"other_data":{很多键值对（控件上的数据）}}
# #                {"core_data":ctx,"other_data":{很多键值对（控件上的数据）}}
# #                 ]
# from dataclasses import dataclass, field
#
# # all_data.pkl=[
# #                {"core_data":{很多键值对（冲突性实例）},other_data":{很多键值对（控件上的数据）}}
# #                {"core_data":{很多键值对（冲突性实例）},other_data":{很多键值对（控件上的数据）}}
# #                {"core_data":{很多键值对（冲突性实例）},other_data":{很多键值对（控件上的数据）}}
# #                 ]
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QWidget, QLayout


# 隐藏文本和图标
# self.tool_button.setText('')  # 隐藏文本
# self.tool_button.setIcon(QIcon())  # 隐藏图标
# setIconVisible(False)

# clicked_button = self.sender()  # 获取发射信号的控件



# import sys
# from PyQt5.QtWidgets import (
#     QApplication, QWidget, QPushButton, QVBoxLayout, QLineEdit,
#     QHBoxLayout, QSpacerItem, QSizePolicy
# )
# from PyQt5.QtCore import Qt
#
#
# class VirtualKeyboard(QWidget):
#     def __init__(self):
#         super().__init__()
#         self.init_ui()
#
#     def init_ui(self):
#         # 默认状态为小写
#         self.is_uppercase = False
#         self.is_number_mode = False
#
#         # 主布局
#         self.main_layout = QVBoxLayout()
#         self.input_line = QLineEdit()
#         self.keyboard_layout = QVBoxLayout()
#
#         self.main_layout.addWidget(self.input_line)
#         self.main_layout.addLayout(self.keyboard_layout)
#         self.setLayout(self.main_layout)
#
#         # 初始化键盘
#         self.init_keyboard()
#
#     def clear_layout(self, layout):
#         """清空布局中的所有控件"""
#         while layout.count():
#             item = layout.takeAt(0)
#             widget = item.widget()
#             if widget is not None:
#                 widget.deleteLater()  # 删除控件
#             elif item.layout() is not None:
#                 self.clear_layout(item.layout())
#
#     def init_keyboard(self):
#         """初始化键盘布局"""
#         # 清空现有布局，避免重复堆叠
#         self.clear_layout(self.keyboard_layout)
#
#         # 按键布局
#         keys_lowercase = [
#             ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
#             ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
#             ['z', 'x', 'c', 'v', 'b', 'n', 'm'],
#         ]
#         keys_uppercase = [
#             ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
#             ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
#             ['Z', 'X', 'C', 'V', 'B', 'N', 'M'],
#         ]
#         keys_numbers = [
#             ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
#             ['!', '@', '#', '¥', '%', '&', '*', '(', ')'],
#             ['~', '-', '_', '+', '=', '[', ']', ';', ':', '?'],
#         ]
#
#         # 根据模式选择按键
#         if self.is_number_mode:
#             keys = keys_numbers
#         else:
#             keys = keys_uppercase if self.is_uppercase else keys_lowercase
#
#         # 添加每一行按键
#         for row_idx, row_keys in enumerate(keys):
#             row_layout = QHBoxLayout()
#
#             # 如果是第二行，添加左右空白占位符实现居中
#             if row_idx == 1:
#                 row_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
#
#             for key in row_keys:
#                 btn = QPushButton(key)
#                 btn.clicked.connect(lambda _, text=key: self.key_pressed(text))
#                 row_layout.addWidget(btn)
#
#             if row_idx == 1:
#                 row_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
#
#             # 在第三行两侧添加 ⇧ 和 ⌫ 按键
#             if row_idx == 2:
#                 shift_btn = QPushButton('⇧')  # Shift 按键
#                 shift_btn.clicked.connect(self.toggle_case)
#                 row_layout.insertWidget(0, shift_btn)  # 添加到行首
#
#                 backspace_btn = QPushButton('⌫')  # Backspace 按键
#                 backspace_btn.clicked.connect(self.backspace)
#                 row_layout.addWidget(backspace_btn)  # 添加到行尾
#
#             self.keyboard_layout.addLayout(row_layout)
#
#         # 添加最后一行功能按键
#         func_layout = QHBoxLayout()
#
#         clr_btn = QPushButton('CLR')
#         clr_btn.clicked.connect(self.clear_input)
#         func_layout.addWidget(clr_btn)
#
#         number_btn = QPushButton('123')
#         number_btn.clicked.connect(self.toggle_number_mode)
#         func_layout.addWidget(number_btn)
#
#         space_btn = QPushButton('⎵')  # 空格键使用特殊符号
#         space_btn.clicked.connect(lambda: self.key_pressed(' '))
#         func_layout.addWidget(space_btn, stretch=2)
#
#         enter_btn = QPushButton('↵')
#         enter_btn.clicked.connect(self.clear_input)
#         func_layout.addWidget(enter_btn)
#
#         esc_btn = QPushButton('ESC')
#         esc_btn.clicked.connect(self.close_keyboard)
#         func_layout.addWidget(esc_btn)
#
#         self.keyboard_layout.addLayout(func_layout)
#
#     def key_pressed(self, key):
#         """将按键输入到输入框中"""
#         current_text = self.input_line.text()
#         self.input_line.setText(current_text + key)
#
#     def backspace(self):
#         """删除输入框中的最后一个字符"""
#         current_text = self.input_line.text()
#         self.input_line.setText(current_text[:-1])
#
#     def clear_input(self):
#         """清空输入框"""
#         self.input_line.clear()
#
#     def toggle_case(self):
#         """切换大小写模式"""
#         self.is_uppercase = not self.is_uppercase
#         self.init_keyboard()
#
#     def toggle_number_mode(self):
#         """切换数字模式"""
#         self.is_number_mode = not self.is_number_mode
#         self.init_keyboard()
#
#     def close_keyboard(self):
#         """关闭键盘窗口"""
#         self.close()
#
# # # 设置布局内所有控件居中
# # layout.setAlignment(Qt.AlignCenter)
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     keyboard = VirtualKeyboard()
#     keyboard.setWindowTitle("虚拟键盘")
#     keyboard.setWindowFlags(Qt.WindowStaysOnTopHint)  # 窗口置顶
#     keyboard.show()
#     sys.exit(app.exec_())






# class VirtualKeyboard(QWidget):
#     def __init__(self):
#         super().__init__()
#
#     def key_clicked(self):
#         clicked_key_text = self.sender().text()
#
#     def close_keyboard(self):
#         self.close()
#
# from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
#
# class MyWindow(QWidget):
#     def __init__(self):
#         super().__init__()
#
#         # 创建主布局
#         main_layout = QVBoxLayout(self)
#
#         # 创建控件
#         button1 = QPushButton("按钮 1")
#
#         button2 = QPushButton("按钮 2")
#         label1 = QLabel("标签 1")
#
#         # 创建子布局
#         sub_layout = QHBoxLayout()
#         sub_button1 = QPushButton("子布局按钮 1")
#         sub_button2 = QPushButton("子布局按钮 2")
#         sub_layout.addWidget(sub_button1)
#         sub_layout.addWidget(sub_button2)
#
#         # 将控件和子布局添加到主布局
#         main_layout.addWidget(button1)
#         main_layout.addWidget(button2)
#         main_layout.addWidget(label1)
#         main_layout.addLayout(sub_layout)
#
#         self.setWindowTitle("控件和布局遍历")
#         self.resize(300, 200)
#
#     def traverse(self, parent):
#         """
#         遍历父控件的所有子控件和布局。
#         """
#         # 遍历父控件的所有子控件
#         # findChildren(self, T, name='', includeInactive=False)
#
#         # 遍历父控件的所有布局
#         if isinstance(parent, QWidget):
#             for i in range(parent.layout().count()):  # 通过 layout 获取子控项
#                 item = parent.layout().itemAt(i)
#                 if item:
#                     if item.widget():
#                         print(f"控件: {item.widget().text()}")
#                     elif item.layout():
#                         print(f"布局: {item.layout()}")
#
#     def showEvent(self, event):
#         # 在窗口显示后遍历窗口中的控件和布局
#         self.traverse(self)
#
# if __name__ == '__main__':
#     app = QApplication([])
#     window = MyWindow()
#     window.show()
#     app.exec_()




from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton

app = QApplication([])

window = QWidget()
layout = QVBoxLayout()

button1 = QPushButton("Button 1")
button2 = QPushButton("Button 2")

layout.addWidget(button1)
layout.addWidget(button2)

# 设置布局的最大尺寸
layout.setMaximumSize(300, 300)

window.setLayout(layout)
window.show()

app.exec_()

# ui转py
# pyuic5 keyboard.ui -o keyboard.py

# py转ts
# pylupdate5 translate_test.py -ts translate_test.ts

# qrc转py
# pyrcc5 resources.qrc -o resources.py

# 激活conda
# conda activate autobalance






























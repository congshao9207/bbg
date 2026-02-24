# @Time : 2/22/22 2:56 PM 
# @Author : lixiaobo
# @File : trans_file_context.py 
# @Software: PyCharm
import os


class TransFileContext(object):
    def __init__(self):
        self.file_abs_path = []

    def attach(self, file_path):
        if file_path:
            self.file_abs_path.append(file_path)

    def teardown(self):
        for item in self.file_abs_path:
            if os.path.exists(item):
                os.remove(item)
        self.file_abs_path.clear()


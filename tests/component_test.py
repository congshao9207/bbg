# @Time : 2/22/22 1:55 PM 
# @Author : lixiaobo
# @File : component_test.py 
# @Software: PyCharm
from component.excel_file_adapter import ExcelFileAdapter


def test_excel_file():
    efa = ExcelFileAdapter("csv", "resource/1.csv")
    dest = efa.to_xlsx()
    print("dest: ", dest)


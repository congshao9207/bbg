# @Time : 2/21/22 7:33 PM 
# @Author : lixiaobo
# @File : ExcelFileAdapter.py 
# @Software: PyCharm
import csv
import csv23

from openpyxl import Workbook
from xls2xlsx import XLS2XLSX

from config.file_type import FileTypeEnum
from excepts.exceptions import ServerException
from util.file_util import obtain_new_file_path


class ExcelFileAdapter(object):
    def __init__(self, ext, file_path):
        self.ext = ext
        self.file_path = file_path

    def to_xlsx(self):
        if self.ext == FileTypeEnum.XLSX.value:
            return self.file_path

        new_file_path = obtain_new_file_path(FileTypeEnum.XLSX)
        if self.ext == FileTypeEnum.XLS.value:
            x2x = XLS2XLSX(self.file_path)
            x2x.to_xlsx(new_file_path)
            return new_file_path
        elif self.ext == FileTypeEnum.CSV.value:
            self.__csv_processor(new_file_path)
            return new_file_path
        else:
            raise ServerException(description="Unsupported file type:" + self.ext)

    def __csv_processor_bak(self, new_file_path):
        with open(self.file_path, "r") as f:
            reader = csv.reader(f)
            wb = Workbook()
            ws = wb.active
            for item in reader:
                ws.append(item)
            wb.save(new_file_path)

    def __csv_processor(self, new_file_path):
        with csv23.open_csv(self.file_path) as reader:
            wb = Workbook()
            ws = wb.active
            for rows in reader:
                ws.append(rows)
            wb.save(new_file_path)
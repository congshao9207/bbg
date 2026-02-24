# @Time : 4/16/22 2:10 PM 
# @Author : lixiaobo
# @File : ocr_result_to_xlsx.py 
# @Software: PyCharm
import time

from openpyxl import Workbook

from config.file_type import FileTypeEnum
from logger.logger_util import LoggerUtil
from util.file_util import obtain_new_file_path
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

logger = LoggerUtil().logger(__name__)


class OcrResultToXlsx(object):
    def __init__(self, flow_data):
        self.flow_data = flow_data
        self.result_file_path = None

    def pre_convert(self):
        self.result_file_path = obtain_new_file_path(FileTypeEnum.XLSX)

    def to_xlsx(self):
        self.pre_convert()
        wb = None
        try:
            wb = Workbook()
            ws = wb.active
            start_time = time.time()
            for page in self.flow_data:
                keys = page.keys()
                index_keys = map(lambda x: int(x), keys)
                sorted_keys = sorted(index_keys)
                for row_num in sorted_keys:
                    row = page[str(row_num)]
                    cell_data = []
                    for cell in row:
                        if cell["text"] is not None:
                            cell["text"] = cell["text"].replace(chr(65535), "")
                        cell_data.append(ILLEGAL_CHARACTERS_RE.sub(r"", cell["text"]) if cell["text"] is not None else None)
                    ws.append(cell_data)
            wb.save(self.result_file_path)
            cost_time_mill = (time.time() - start_time) * 1000
            logger.info("to_xlsx, file_path:%s, cost_time: %f", self.result_file_path, cost_time_mill)
        finally:
            if wb:
                wb.close()
        return self.result_file_path

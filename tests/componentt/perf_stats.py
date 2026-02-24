import time

from openpyxl import Workbook


class PerfStats(object):
    def __init__(self):
        self.file_name = time.strftime("perf_stats_%Y_%m_%d.xlsx", time.localtime())
        self.per_data = None

        self.wb = Workbook()
        self.ws = self.wb.active

    def add_per_data(self, *data):
        self.per_data = data

    def add_stats(self, cost):
        row_data = [x for x in self.per_data]
        row_data.append(cost)
        self.ws.append(row_data)
        self.wb.save(self.file_name)

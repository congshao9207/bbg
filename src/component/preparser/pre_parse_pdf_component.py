from typing import List

import pdfplumber
from pdfminer.pdfpage import PDFPage
from pdfplumber.page import Page

from component.preparser.pre_parse_cfg import kw_bank_account, kw_user_name, kw_row_count, kw_bank_name_d
from component.preparser.pre_parse_util import parse_join_info_field, parse_start_end, parse_bank_name
from logger.logger_util import LoggerUtil
import re
from config.column_mapping import CHAR_MAPPING

logger = LoggerUtil().logger(__name__)


class PreParsePdfComponent(object):

    def __init__(self, ctx):
        self.ctx = ctx

    def pre_parse(self):
        logger.info("begin pre parse......:%s", self.ctx.stand_file_name)
        with pdfplumber.open(self.ctx.stand_file_path, password=self.ctx.file_pwd) as pdf:
            first_page = self._fetch_first_page(pdf)
            texts = first_page.extract_text(x_tolerance=1)
            rows = texts.split("\n")
            for k, v in CHAR_MAPPING.items():
                rows = [row.replace(v[0], k) for row in rows]
            self.parse_head_field(rows)

            if self._vote_extract_table():
                rows = self._extract_table_info(first_page)
                if rows:
                    for k, v in CHAR_MAPPING.items():
                        rows = [row.replace(v[0], k) for row in rows]
                    self.parse_head_field(rows)

    def parse_head_field(self, rows):
        index = -1
        for row in rows:
            row = re.sub('[a-zA-Z/\n]', '', row)
            index += 1
            try:
                if not self.ctx.bank_name and index <= 2:
                    self.ctx.bank_name = parse_bank_name(row)
                    if self.ctx.bank_name == '':
                        self.ctx.bank_name = self._parse_field(row, kw_bank_name_d)
                    if self.ctx.bank_name in ['交易用途']:
                        self.ctx.bank_name = ''
                    self.ctx.bank_name = re.sub('[^\u4e00-\u9fa5]', '', self.ctx.bank_name)
                if not self.ctx.bank_account:
                    self.ctx.bank_account = self._parse_field(row, kw_bank_account)
                    self.ctx.bank_account = re.sub('[\u4e00-\u9fa5]', '', self.ctx.bank_account)
                if not self.ctx.user_name:
                    self.ctx.user_name = self._parse_field(row, kw_user_name)
                    self.ctx.user_name = re.sub('[^\u4e00-\u9fa5]', '', self.ctx.user_name)
                if not self.ctx.start_date or not self.ctx.end_date:
                    start, end = parse_start_end(row)
                    if not self.ctx.start_date:
                        self.ctx.start_date = start
                    if not self.ctx.end_date:
                        self.ctx.end_date = end
                if not self.ctx.row_count:
                    self.ctx.row_count = self._parse_field(row, kw_row_count)
                    self.ctx.row_count = re.sub(r'\D', '', self.ctx.row_count)
            except Exception as e:
                logger.error(e)

        if not self.ctx.is_parse_succeed():
            logger.warn("parse failed, origin data:%s", rows)

    @staticmethod
    def _parse_field(row, kws, no_title=False, x_tolerance=0):
        return parse_join_info_field(row, kws, no_title=no_title, x_tolerance=x_tolerance)

    def _vote_extract_table(self):
        count = 0
        if not self.ctx.bank_name:
            count += 1
        if not self.ctx.bank_account:
            count += 1
        if not self.ctx.user_name:
            count += 1
        return count >= 2

    @staticmethod
    def _extract_table_info(first_page):
        tables = first_page.extract_table()
        if not tables or len(tables) > 6 or (tables[0] and len(tables[0]) > 4):
            return None

        row_val = []
        for row in tables:
            row_con = ''
            i = 0
            for cell in row:
                i += 1
                if cell:
                    info = cell.split("\n")
                    r = info[0] if info else info
                    row_con += r
                    if i % 2 == 0:
                        row_con += '  '
                    else:
                        row_con += ':'

            row_val.append(row_con)
        return row_val

    @staticmethod
    def _fetch_first_page(pdf):
        for i, page in enumerate(PDFPage.create_pages(pdf.doc)):
            return Page(pdf, page, page_number=1, initial_doctop=0)
        return None

import datetime
import re
from functools import reduce

import openpyxl

from component.preparser.pre_parse_cfg import kw_user_name, kw_start, kw_end, kw_row_count, kw_sep, \
    x_kw_bank_account, trans_header_max_rows, ignore_content
from component.preparser.pre_parse_util import parse_join_info_field, is_traversed_title, parse_start_end, \
    parse_bank_name
from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)


def decl_field_val(fun):
    def warp(self, *args, **kwargs):
        v = fun(self, *args, **kwargs)
        if v and type(v) == datetime.datetime:
            return v.strftime("%Y-%m-%d")
        return v
    return warp


class PreParseCsvComponent(object):
    def __init__(self, ctx):
        self.ctx = ctx

    def pre_parse(self):
        pass

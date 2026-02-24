import traceback

from component.preparser.pre_parse_context import PreParseContext
from component.preparser.pre_parse_pdf_component import PreParsePdfComponent
from component.preparser.pre_parse_xlsx_component import PreParseXlsxComponent
from component.preparser.pre_parse_csv_component import PreParseCsvComponent
from component.preparser.pre_parse_xls_component import PreParseXlsComponent
from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)


class PreParseScheduler(object):
    def __init__(self):
        self.components = {
            "pdf": PreParsePdfComponent,
            "xlsx": PreParseXlsxComponent,
            "csv": PreParseCsvComponent,
            "xls": PreParseXlsComponent
        }

    def dispatch_pre_parse(self, file, file_pwd) -> (int, str, object):
        with PreParseContext(file, file_pwd if file_pwd else '') as ctx:
            key = ctx.ext.lower()
            component_cls = self.components.get(key)
            res_code = 0
            res_msg = "成功"
            if not component_cls:
                return 1, "pre parser is not support for extension: %s " % key, None
            try:
                component = component_cls(ctx)
                component.pre_parse()
                if not ctx.is_parse_succeed():
                    logger.warn("未提取到数据：%s", str(file))
            except Exception as e:
                logger.error(e)
                e_info = traceback.format_exc()
                logger.warn(e_info)
                res_code = 1
                res_msg = str(e)
            return res_code, res_msg, ctx.build_parse_data()

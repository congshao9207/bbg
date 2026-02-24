# @Time : 4/16/22 7:38 AM 
# @Author : lixiaobo
# @File : ocr_client.py 
# @Software: PyCharm
import traceback

import requests
from py_eureka_client import eureka_client

from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)


class OcrClient(object):
    """
    上传接口：/api/pdf/file/upload
    主动获取结果接口：api/pdf/file/result
    """
    def __init__(self, file_path=None, resp_json=None, group_no=None, parse_no=None):
        self.file_path = file_path
        self.resp_json = resp_json
        self.group_no = group_no
        self.parse_no = parse_no
        self.cause = None

    def call_back_upload(self, url):
        full_url = url + "api/pdf/file/upload"
        logger.info("request ocr, url: %s", full_url)

        with open(self.file_path, 'rb') as f:
            files = {'file': f}
            resp = requests.post(url=full_url, data={"groupNo": self.group_no}, files=files)
            logger.info("ocr response status code:%s, msg:%s", str(resp.status_code), resp.text)
            self._parse_resp(resp)

    def call_back_result_query(self, url):
        full_url = url + "api/pdf/file/result"
        logger.info("result_query, url: %s", full_url)
        resp = requests.get(url=full_url, params={"parseNo": self.parse_no})

        logger.info("result_query response status code:%s", str(resp.status_code))
        self._parse_resp(resp)

    def _parse_resp(self, resp):
        if resp.status_code != 200:
            self.cause = "Ocr server error, status_code:" + str(resp.status_code)
            return

        self.resp_json = resp.json()
        if not self.resp_json:
            return

        if self.resp_json["resCode"] != 0:
            self.cause = self.resp_json["resMsg"]
            return
        self.parse_no = self.resp_json["data"]["parseNo"]

    def ocr(self, func):
        logger.info("begin Pdf-parser node ")
        try:
            eureka_client.walk_nodes("BRAINSPALMS", walker=func)
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error("ocr exception, %s", stack_trace)
            self.cause = "OCR Exception:" + str(e)
        logger.info("end Pdf-parser node ")

        return self.cause, self.parse_no, self.resp_json

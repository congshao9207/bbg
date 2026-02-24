# @Time : 4/17/22 2:43 PM
# @Author : lixiaobo
# @File : ocr_result_to_xlsx_test.py
# @Software: PyCharm
import json

from file_utils.files import file_content

from ocr.ocr_result_to_xlsx import OcrResultToXlsx


def test_json_to_xlsx():
    str_json = file_content("../resource", "ocr_json.json")
    json_obj = json.loads(str_json)
    flow_data = json_obj["data"]["result"]

    converter = OcrResultToXlsx(flow_data)
    result_file_path = converter.to_xlsx()
    print(result_file_path)


def test_json_to_xlsx1():
    str_json = file_content("../resource", "ocr_json_line.json")
    json_obj = json.loads(str_json)

    converter = OcrResultToXlsx(json_obj)
    result_file_path = converter.to_xlsx()
    print(result_file_path)


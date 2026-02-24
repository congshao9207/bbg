# @Time : 2/22/22 9:24 AM
# @Author : lixiaobo
# @File : ctrl_test.py
# @Software: PyCharm
import json
import logging
import time

from file_utils.files import resource_content


def trans_file_upload(client, file_name, param_path, app_id="0000000000"):
    with open('../resource/' + file_name, 'rb') as f:
        with open("../resource/" + param_path) as cf:
            param = cf.read()
            params = {
                "file": (f, file_name),
                'appId': app_id,
                'param': param,
                'content_type': 'text/csv'
            }
            return client.post('/trans/upload', data=params, content_type='multipart/form-data')


def trans_task_query(client, out_req_no, app_id="0000000000"):
    data = {
        'appId': app_id,
        'outReqNo': out_req_no,
        'timestamp': str(int(time.time()))
    }

    msg = json.dumps(data)

    return client.post('/trans/query', data=msg, content_type='application/json')


def test_upload_file(client):
    file_name = "农行流水.xlsx"
    param_path = "农行流水.json"
    res = trans_file_upload(client, file_name, param_path)
    assert res.status_code == 200

    v = res.get_json()
    print(json.dumps(v))


def test_query_task(client):
    res = trans_task_query(client, "54389754379272")
    v = res.get_json()
    print(json.dumps(v))


logging.getLogger('pdfminer').setLevel(logging.ERROR)


def test_pre_parse(client):
    with open("../resource/pdf/ali_pay_1.pdf", 'rb') as f:
        params = {
            "file": (f, 'ali_pay_1.pdf'),
            'content_type': 'text/csv'
        }
        resp = client.post('/trans/pre-parse', data=params, content_type='multipart/form-data')
        print(json.dumps(resp.get_json()))

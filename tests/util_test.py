# @Time : 2/15/22 2:33 PM
# @Author : lixiaobo
# @File : util_test.py
# @Software: PyCharm
import codecs
import hashlib

import chardet
import pandas as pd
from json2obj import JSONObjectMapper
from json2object import jsontoobject as jo

from config.res_code import ResCodeEnum
from config.trans_config import MAX_TITLE_NUMBER
from entity.resp_entity import RespEntity
from excepts.exceptions import ParseException
from util.distributed_lock_proxy import DistributedLockProxy
from util.magfin_redis import redis_conn


def test_format():
    info = "mysql+pymysql://%s:%s@localhost/trans_parser" % ("root", "ysyhl9t!")
    print(info)


def test_json_dumps():
    info = RespEntity.response(0, "Trans parser is running!")
    print(info)


def test_json_dumps():
    v = ResCodeEnum.SUCCESS.value
    print(ResCodeEnum.SUCCESS.value[0])
    info = RespEntity.with_res_enum(ResCodeEnum.SUCCESS)
    print(info)


def test_json_obj_mapper():
    person = JSONObjectMapper("""{
            "name" : "trumpowen" ,
            "age" : 125
        }""")
    print(person.name)


def test_json_object():
    class Student:
        def __init__(self):
            self.firstName = None
            self.lastName = None
            self.courses = [Course('')]

    class Course:
        def __init__(self, name):
            self.name = name

    data = '''{
    "firstName": "James",
    "lastName": "Bond",
    "courses": [{
        "name": "Fighting"},
        {
        "name": "Shooting"}
        ]
    }
    '''

    model = Student()
    result = jo.deserialize(data, model)
    print(result.courses[0].name)


def test_calc_md5():
    md5hash = hashlib.md5("Hello".encode("utf-8"))
    md5 = md5hash.hexdigest()
    print(md5)


def test_exception():
    try:
        raise ParseException("parse error")
    except Exception as e:
        print(str(e))


def test_read_df():
    file_path = "/Users/xiaoboli/Sources/trans-parser/src/8f1f1c9e-9516-11ec-96d6-88e9fe77c07d.xlsx"
    with open(file_path, "rb") as file:
        try:
            title_df = pd.read_excel(file, skiprows=range(MAX_TITLE_NUMBER, 100000), header=None, engine='openpyxl')
            print("title_df", title_df)
        except Exception as e:
            print("error:", e)


def test_redis():
    redis_conn.set("info", "base info")
    v = redis_conn.get("info")
    print("v:", v)


def test_lock():
    lock = DistributedLockProxy(redis_conn, "group_no_0001")
    res = lock.acquire_no_block()

    lock1 = DistributedLockProxy(redis_conn, "group_no_0001")
    res1 = lock1.acquire()
    print("res1:", res1)


def test_sort():
    info = {"3": "a", "2":"b", "4":"c"}
    print(info.keys())
    print(type(sorted(info.keys(), reverse=True)))


def test_basic():
    info = ["aa", "bb", None, "cc"]
    b = [x + "aaa" for x in info if x]
    print(b)

# @Time : 2/22/22 11:25 AM 
# @Author : lixiaobo
# @File : model_test.py 
# @Software: PyCharm
from flask_sqlalchemy_session import current_session

from model.model import SysInfo


def test_filter(client):
    res = client.get("/")
    print(str(res.data))

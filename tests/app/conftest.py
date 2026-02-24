# -*- coding: utf-8 -*-
# @Author : lixiaobo
# @File : conftest.py.py
# @Software: PyCharm

import pytest

from app import app


@pytest.fixture
def client():
    client = app.test_client()
    yield client

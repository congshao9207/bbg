import logging
import re
import time

import pytest

from component.preparser.pre_parse_scheduler import PreParseScheduler
from componentt.perf_stats import PerfStats

logging.getLogger('pdfminer').setLevel(logging.ERROR)
pdf_file_path_list = [
    ["10920.pdf", 1],
    ["10942.pdf", 1],
    ["10945.pdf", 1],
    ["10946.pdf", 1],
    ["10947.pdf", 1],
    ["10954.pdf", 1],
    ["10955.pdf", 1],
    ["10960.pdf", 1],
    ["10967.pdf", 1],
    ["10968.pdf", 1],
    ["10969.pdf", 1],
    ["10970.pdf", 1],
    ["10979.pdf", 1],
    ["10982.pdf", 1],
    ["10985.pdf", 1],
    ["11006.pdf", 1],
    ["11009.pdf", 1],
    ["11010.pdf", 1],
    ["11011.pdf", 1],
    ["11012.pdf", 1],
    ["11013.pdf", 1],
    ["11014.pdf", 1],
    ["11015.pdf", 1],
    ["11016.pdf", 1],
    ["11042.pdf", 1],
    ["11045.pdf", 1],
    ["11049.pdf", 1],
    ["11061.pdf", 1],
    ["11064.pdf", 1],
    ["11067.pdf", 1],
    ["11068.pdf", 1],
    ["11073.pdf", 1],
    ["11076.pdf", 1],
    ["11079.pdf", 3],
    ["11108.pdf", 1],
    ["11112.pdf", 1],
    ["11118.pdf", 1],
    ["11130.pdf", 1],
    ["11131.pdf", 1],
    ["11136.pdf", 1],
    ["11137.pdf", 1],
    ["11138.pdf", 1],
    ["11145.pdf", 1],
    ["11212.pdf", 1],
    ["11215.pdf", 1],
    ["11221.pdf", 1],
    ["11224.pdf", 1],
    ["11228.pdf", 1],
    ["11231.pdf", 1],
    ["11234.pdf", 1],
    ["11237.pdf", 1],
    ["11238.pdf", 1],
    ["11247.pdf", 1],
    ["11248.pdf", 1],
    ["11253.pdf", 1],
    ["11257.pdf", 1],
    ["11262.pdf", 1],
    ["11268.pdf", 1],
    ["11272.pdf", 1],
    ["11273.pdf", 1],
    ["11274.pdf", 1],
    ["11291.pdf", 1],
    ["11294.pdf", 1],
    ["11295.pdf", 1],
    ["11300.pdf", 1],
    ["11303.pdf", 1],
    ["11304.pdf", 1],
    ["11314.pdf", 1],
    ["11317.pdf", 1],
    ["11324.pdf", 1],
    ["11325.pdf", 1],
    ["11330.pdf", 1],
    ["11334.pdf", 1],
    ["11337.pdf", 1],
    ["11338.pdf", 1],
    ["11339.pdf", 1],
    ["11346.pdf", 1],
    ["11350.pdf", 1],
    ["11363.pdf", 1],
    ["11371.pdf", 1],
    ["11372.pdf", 1],
    ["11373.pdf", 1],
    ["11374.pdf", 1],
    ["11376.pdf", 1],
    ["11392.pdf", 1],
    ["11395.pdf", 1],
    ["11402.pdf", 1],
    ["11406.pdf", 1],
    ["11407.pdf", 1],
    ["11410.pdf", 1],
    ["11415.pdf", 1],
    ["11429.pdf", 1],
    ["11432.pdf", 1],
    ["11435.pdf", 1],
    ["11438.pdf", 1],
    ["11441.pdf", 1],
    ["11456.pdf", 1],
    ["11461.pdf", 1],
    ["11464.pdf", 1],
    ["11468.pdf", 1],
    ["a1.pdf", 2],
    ["ali_pay_1.pdf", 2],
    ["ali_pay_2.pdf", 2],
    ["ali_pay_3.pdf", 2],
    ["ali_pay_4.pdf", 2],
    ["ali_pay_5.pdf", 2],
    ["wechat.pdf", 2],
]

xlsx_file_path_list = [
    ["10326.xlsx", 1],
    ["10341.xlsx", 1],
    ["10342.xlsx", 1],
    ["10440.xlsx", 1],
    ["10476.xlsx", 1],
    ["10481.xlsx", 1],
    ["10592.xlsx", 1],
    ["10593.xlsx", 1],
    ["10842.xlsx", 1],
    ["10843.xlsx", 1],
    ["10844.xlsx", 1],
    ["10845.xlsx", 1],
    ["10900.xlsx", 1],
    ["10901.xlsx", 1],
    ["10902.xlsx", 1],
    ["10903.xlsx", 1],
    ["10963.xlsx", 1],
    ["10964.xlsx", 1],
    ["10965.xlsx", 1],
    ["10966.xlsx", 1],
    ["10988.xlsx", 1],
    ["10989.xlsx", 1],
    ["11036.xlsx", 1],
    ["11037.xlsx", 1],
    ["11038.xlsx", 1],
    ["11048.xlsx", 1],
    ["11116.xlsx", 1],
    ["11117.xlsx", 1],
    ["11121.xlsx", 1],
    ["11122.xlsx", 1],
    ["11123.xlsx", 1],
    ["11124.xlsx", 1],
    ["11125.xlsx", 1],
    ["11126.xlsx", 1],
    ["11127.xlsx", 1],
    ["11128.xlsx", 1],
    ["11129.xlsx", 1],
    ["11218.xlsx", 1],
    ["11219.xlsx", 1],
    ["11220.xlsx", 1],
    ["11245.xlsx", 1],
    ["11246.xlsx", 1],
    ["11256.xlsx", 1],
    ["11258.xlsx", 1],
    ["11261.xlsx", 1],
    ["11265.xlsx", 1],
    ["11266.xlsx", 1],
    ["11267.xlsx", 1],
    ["11271.xlsx", 1],
    ["11277.xlsx", 1],
    ["11309.xlsx", 1],
    ["11310.xlsx", 1],
    ["11312.xlsx", 1],
    ["11313.xlsx", 1],
    ["11320.xlsx", 1],
    ["11321.xlsx", 1],
    ["11322.xlsx", 1],
    ["11333.xlsx", 1],
    ["11349.xlsx", 1],
    ["11353.xlsx", 1],
    ["11354.xlsx", 1],
    ["11355.xlsx", 1],
    ["11356.xlsx", 1],
    ["11357.xlsx", 2],
    ["11358.xlsx", 2],
    ["11359.xlsx", 2],
    ["11360.xlsx", 2],
    ["11361.xlsx", 2],
    ["11362.xlsx", 2],
    ["11366.xlsx", 2],
    ["11367.xlsx", 2],
    ["11368.xlsx", 2],
    ["11369.xlsx", 2],
    ["11370.xlsx", 2],
    ["11405.xlsx", 2],
    ["11418.xlsx", 2],
    ["11419.xlsx", 2],
    ["11420.xlsx", 2],
    ["11421.xlsx", 2],
    ["11422.xlsx", 2],
    ["11423.xlsx", 2],
    ["11424.xlsx", 2],
    ["11425.xlsx", 2],
    ["11426.xlsx", 2],
    ["11428.xlsx", 2],
    ["11444.xlsx", 2],
    ["11445.xlsx", 2],
    ["11446.xlsx", 2],
    ["11447.xlsx", 2],
    ["11448.xlsx", 2],
    ["11449.xlsx", 2],
    ["11450.xlsx", 2],
    ["11451.xlsx", 2],
    ["11452.xlsx", 2],
    ["11453.xlsx", 2],
    ["11454.xlsx", 2],
    ["11455.xlsx", 2],
    ["11467.xlsx", 2],
    ["11471.xlsx", 3],
    ["11472.xlsx", 3],
]


ps = PerfStats()


@pytest.fixture()
def perf_stats():
    start = time.time() * 1000
    yield ps
    cost_mill = time.time() * 1000 - start
    ps.add_stats(int(cost_mill))


@pytest.mark.usefixtures("perf_stats")
@pytest.mark.parametrize('file_path', list(filter(lambda x: x[1] <= 3, pdf_file_path_list)))
def test_pre_parse_pdf(file_path, perf_stats):
    data = _pre_parse("../resource/pdf/" + file_path[0])
    perf_stats.add_per_data(file_path[0], str(data))


@pytest.mark.usefixtures("perf_stats")
@pytest.mark.parametrize('file_path', list(filter(lambda x: x[1] <= 3, xlsx_file_path_list)))
def test_pre_parse_xlsx(file_path, perf_stats):
    data = _pre_parse("../resource/xlsx/" + file_path[0])
    perf_stats.add_per_data(file_path[0], str(data))


def _pre_parse(file_path):
    pps = PreParseScheduler()
    res_code, res_msg, data = pps.dispatch_pre_parse(file_path, None)
    print("file_path: ", file_path)
    print("res_code: ", res_code)
    print("res_msg: ", res_msg)
    print("data ", data)
    return data


def test_re():
    reg = "[\\d]{4}-[\\d]{2}-[\\d]{2}[\\s\\-\\—]+[\\d]{4}-[\\d]{2}-[\\d]{2}"
    info = '2021-10-26——2022-10-25'
    res = re.findall(reg, info)
    print("res:", res)

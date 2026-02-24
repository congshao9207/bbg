import re
import time
from functools import reduce

from component.preparser.pre_parse_cfg import kw_sep, reg_to_format, kw_stop_flag, trans_title_min_cols, \
    trans_title_max_cols, kw_start_end, kw_start_end_no_title, re_start_end_date, kw_start, kw_end, kw_bank_name


def parse_join_info_field(row, kws, no_title=False, x_tolerance=0):
    row_info = row
    max_loop = 20
    loop_index = 0
    while True:
        loop_index += 1
        if loop_index > max_loop:
            break
        res, span = _parse_join_info_field(row_info, kws, no_title, x_tolerance)
        if not res and span:
            row_info = row_info[span[1]:]
        else:
            return res
    return ''


def _parse_join_info_field(row, kws, no_title=False, x_tolerance=0):
    kws, exclude = (kws, None) if type(kws) is list else (kws["include"], kws["exclude"])
    last_span = None
    for kw in kws:
        r = re.search(kw, row)
        if not r:
            continue

        last_span = r.span()
        is_exclude = _is_exclude(row, r.span(), exclude)
        if not is_exclude:
            continue
        if no_title:
            infos = row[r.span()[0]:]
        else:
            infos = row[r.span()[1]:]
        res = ''
        space_c = 0
        invalid_sep_flag = False
        for ch in infos:
            if ch == ' ':
                space_c += 1
            else:
                invalid_sep_flag |= '0' <= ch <= '9'
                space_c = 0
            if ch in kw_stop_flag:
                break
            if len(res) > 1 and ch == ' ' and space_c > x_tolerance:
                break
            if not res and ch == ' ':
                continue
            if ch not in kw_sep:
                res += ch
            elif not invalid_sep_flag:
                res = ''
        return res.strip(), last_span
    return '', last_span


def is_traversed_title(row_val):
    if len(row_val) < trans_title_min_cols:
        return False
    elif len(row_val) > trans_title_max_cols:
        return True

    row_con = reduce(lambda e1, e2: e1 + e2, list(filter(lambda x: x and type(x) == str, row_val)))
    if not row_con:
        return False
    print(row_con)
    res = re.search('[\\d]+', row_con)
    return res is None


def parse_bank_name(row):
    for kw in kw_bank_name:
        index = row.find(kw)
        if index > -1:
            res = row[:index + len(kw)]
            reversed_info = res.strip()[::-1]
            m = re.search("[\\:\\：\\s]", reversed_info)
            if m:
                res = reversed_info[:m.span()[1]][::-1]
            return res.strip()
    return ''


def parse_start_end(row):
    start_info = ''
    end_info = ''
    info = parse_join_info_field(row, kw_start_end, x_tolerance=1)
    if not info:
        info = parse_join_info_field(row, kw_start_end_no_title, no_title=True, x_tolerance=2)
    if info:
        for reg in re_start_end_date:
            res = re.findall(reg, info)
            if res:
                start_info = res[0]
                if len(res) > 1:
                    end_info = res[1]
                break
    else:
        info = parse_join_info_field(row, kw_start)
        if info:
            start_info = _match_field(info, start_info)

        info = parse_join_info_field(row, kw_end)
        if info:
            end_info = _match_field(info, end_info)

    return start_info, end_info


def _match_field(info, default_val):
    for reg in re_start_end_date:
        res = re.findall(reg, info)
        if res:
            default_val = res[0] if res else default_val
        if default_val:
            break
    return default_val


def _is_exclude(row, span, exclude):
    if not exclude:
        return True
    for ex in exclude:
        res = re.search(ex, row)
        if not res:
            continue

        ex_span = res.span()
        if ex_span[0] < span[0] < ex_span[1]:
            return False
        elif ex_span[0] < span[1] < ex_span[1]:
            return False
        elif span[0] < ex_span[0] < span[1]:
            return False
        elif span[0] < ex_span[1] < span[1]:
            return False

    return True


def date_time_format(info):
    for reg in reg_to_format:
        if not re.match(reg[0], info):
            continue
        if reg[1]:
            t = time.strptime(info, reg[1])
            return time.strftime("%Y-%m-%d", t)
    return info

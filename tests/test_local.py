# -*- coding: utf-8 -*-
"""本地回归测试：不联网，只测参数校验与电话号码清洗。

运行：python tests/test_local.py
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from create_ticket import create_gdex_ticket, normalize_phone  # noqa: E402

passed, failed = 0, 0


def check(case, fn, expect_code, expect_msg_part=None):
    global passed, failed
    r = fn()
    ok = (r["code"] == expect_code) and (
        expect_msg_part is None or expect_msg_part in r["message"]
    )
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {case}: code={r['code']} ticket_id={r.get('ticket_id')} "
          f"message={r['message'][:60]}")
    if ok:
        passed += 1
    else:
        failed += 1


print("== 1. 电话号码清洗 normalize_phone ==")
for raw, want in [
    ("138-0013-8000", ("13800138000", None)),
    ("138 0013 8000", ("13800138000", None)),
    ("+86 13800138000", ("13800138000", None)),
    ("0086 13800138000", ("13800138000", None)),
    ("8613800138000", ("13800138000", None)),
    ("(021) 6588-1234", ("02165881234", None)),
    ("+60 123456789", ("+60123456789", None)),  # 国际号码宽松放行
    ("abc-defg", ("", "格式不正确")),
    ("", ("", "不能为空")),
]:
    got = normalize_phone(raw)
    ok = got[0] == want[0] and (want[1] is None or (got[1] or "").find(want[1]) >= 0)
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {raw!r} -> {got}")
    if ok:
        passed += 1
    else:
        failed += 1


print()
print("== 2. 参数校验（应全部本地拦截 code=-1，不联网） ==")


def ok_name(**kw):
    base = {"name": "测试", "phone": "13800138000",
            "address": "北京市朝阳区测试路1号", "appointment_time": "2026-11-20"}
    base.update(kw)
    return create_gdex_ticket(**base)


check("姓名为空", lambda: ok_name(name=""), -1, "姓名不能为空")
check("姓名只有空格", lambda: ok_name(name="   "), -1, "姓名不能为空")
check("姓名 None", lambda: ok_name(name=None), -1, "姓名不能为空")
check("电话为空", lambda: ok_name(phone=""), -1, "电话不能为空")
check("电话格式错误", lambda: ok_name(phone="12345"), -1, "格式不正确")
check("电话是字母", lambda: ok_name(phone="abcdefghijk"), -1, "格式不正确")
check("地址为空", lambda: ok_name(address=""), -1, "地点不能为空")
check("时间为空", lambda: ok_name(appointment_time=""), -1, "时间不能为空")
check("时间格式 2026/11/20", lambda: ok_name(appointment_time="2026/11/20"), -1, "YYYY-MM-DD")
check("时间格式 20261120", lambda: ok_name(appointment_time="20261120"), -1, "YYYY-MM-DD")
check("时间带时段 2026-11-20 上午", lambda: ok_name(appointment_time="2026-11-20 上午"), -1, "YYYY-MM-DD")

print()
print("== 3. 模板防呆（TEMPLATE_ID=0 拒绝建单） ==")
import create_ticket as ct  # noqa: E402

_orig = ct.TEMPLATE_ID
ct.TEMPLATE_ID = 0
check("TEMPLATE_ID=0", lambda: ok_name(), -1, "模板未配置")
ct.TEMPLATE_ID = _orig

print()
print(f"结果：{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)

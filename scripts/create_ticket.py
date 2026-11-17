"""
GDEX-demo 上门工单创建脚本 (v1.2.0)

v1.2.0 变更：工单字段从 2 个扩展为 4 个；模板改为 3195（GDEX-ticket）
    - 新增：预约安装地点 → TextField_3783（address）
    - 新增：预约时间 → TextField_2563（Expected delivery date，Udesk 服务端强制 YYYY-MM-DD 格式）
    - 联系电话字段变更：TextField_2556 → TextField_6709（Phone Number）

v1.1.0 变更：切换到 udesk-wofeng.s5 环境
    - API 地址、鉴权账号、token 换为 wofeng 演示环境
    - 平台函数更名为 create_gdex_ticket，避免与其他技能的 create_ticket 重名

平台函数：
    create_gdex_ticket(name, phone, address, appointment_time)

返回 dict：{"code": ..., "message": "...", "ticket_id": ...}
    code == 1000 且 ticket_id 非空：创建成功
    code == -1：参数不合法（message 说明原因）
    code == -2：网络错误
    code == -3：未知错误
    code == -4：请求超时（工单可能已经创建，不要直接重试）
    其他：Udesk 返回的错误码（见 HINTS）

工单标题、内容为固定值；姓名、电话、地点、时间四个变量分别写入自定义字段。
本文件没有命令行入口，不读取环境变量和配置文件；请直接修改下面的配置常量。
"""

import re
import json
import time
import uuid
import hashlib
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ============================================================
# 配置（固定值）
# 注意：下面包含真实 token，请勿把本文件上传到公开仓库或分享给无关人员。
# ============================================================

API_BASE_URL = "https://udesk-wofeng.s5.udesk.cn"
ADMIN_EMAIL = "admin_demo@udesk.cn"
OPEN_API_TOKEN = ""  # 在此填入你的 Udesk API Token（管理后台 → 设置 → 安全设置 → API Token）
TICKETS_ENDPOINT = "/open_api_v1/tickets"

# 工单模板：3195 = GDEX-ticket
# 字段：TextField_2557 Name / TextField_6709 Phone Number / TextField_3783 address /
#       TextField_2563 Expected delivery date
# 模板 ID 为 0 时 create_ticket 会直接拒绝建单，防止 Udesk 静默降级到默认模板导致字段丢失。
TEMPLATE_ID = 3195
FIELD_NAME = "TextField_2557"     # 客户姓名 Name
FIELD_PHONE = "TextField_6709"    # 联系电话 Phone Number
FIELD_ADDRESS = "TextField_3783"  # 预约安装地点 address
FIELD_TIME = "TextField_2563"     # 预约时间 Expected delivery date

TICKET_SUBJECT = "onsite installation"        # 工单标题（固定）
TICKET_CONTENT = "IM-onsite installation"     # 工单内容（固定）

# 可选：工单分派（留空 = 不传，由 Udesk 自身规则处理）
ASSIGNEE_EMAIL = ""       # 受理客服邮箱
AGENT_GROUP_NAME = ""     # 受理客服组名称
PRIORITY = ""             # 优先级中文名：紧急 / 高 / 标准 / 低

TIMEOUT_SECONDS = 30

# Udesk 错误码 -> 处理提示（给 agent 参考，不要原样转述给客户）
HINTS = {
    2059: "签名错误：检查邮箱和 token（已自动尝试 SHA256 与 SHA1）",
    2002: "子域名无效：检查 API_BASE_URL",
    2015: "鉴权账号不是超级管理员",
    2058: "公司不是专业版，无法使用开放接口",
    20621: "时间戳格式错误",
    20622: "本机时间与服务器相差超过 5 分钟",
    20623: "nonce 重复，可重试一次",
    20624: "nonce 为空",
    2000: "请求参数有误：常见为模板、字段、客服、客服组或优先级不存在",
    2005: "资源不存在",
}


# ============================================================
# 签名
# ============================================================

def build_sign(email, token, timestamp, nonce, algo="sha256", sign_version="v2"):
    """签名：HASH(email & token & timestamp & nonce & sign_version)。SHA256 失败时改用 SHA1。"""
    raw_str = f"{email}&{token}&{timestamp}&{nonce}&{sign_version}"
    return getattr(hashlib, algo)(raw_str.encode("utf-8")).hexdigest()


def build_url(algo="sha256"):
    """拼接带鉴权参数的完整 URL。每次调用都生成新的 timestamp 和 nonce。"""
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())
    sign = build_sign(ADMIN_EMAIL, OPEN_API_TOKEN, timestamp, nonce, algo)
    return (
        f"{API_BASE_URL.rstrip('/')}{TICKETS_ENDPOINT}"
        f"?email={ADMIN_EMAIL}"
        f"&timestamp={timestamp}"
        f"&sign={sign}"
        f"&nonce={nonce}"
        f"&sign_version=v2"
    )


# ============================================================
# 参数处理
# ============================================================

def normalize_phone(raw):
    """去掉空格、横线、括号及 +86 前缀。返回 (phone, error)。支持手机号、座机、国际号码。"""
    if not raw or not str(raw).strip():
        return "", "联系电话不能为空"
    p = re.sub(r"[\s\-()（）]", "", str(raw))
    if p.startswith("+86"):
        p = p[3:]
    elif p.startswith("0086"):
        p = p[4:]
    elif p.startswith("86") and len(p) == 13:
        p = p[2:]
    if re.fullmatch(r"1[3-9]\d{9}", p):    # 中国大陆手机号
        return p, None
    if re.fullmatch(r"\+?\d{7,15}", p):    # 座机（含区号）或其他国家号码，宽松放行
        return p, None
    return "", f"联系电话格式不正确：{raw}"


# ============================================================
# 请求
# ============================================================

def _send(payload_bytes, algo):
    """发送一次请求，统一返回 {code, message, ticket_id}。"""
    req = Request(build_url(algo), data=payload_bytes, headers={
        "Content-Type": "application/json; charset=utf-8",
    })
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {
                "code": result.get("code"),
                "message": result.get("message", ""),
                "ticket_id": result.get("ticket_id"),
            }
    except HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")[:300]
        try:  # 鉴权失败等情况，错误码在响应体里
            body = json.loads(text)
            return {"code": body.get("code", e.code),
                    "message": str(body.get("message", text)), "ticket_id": None}
        except Exception:
            return {"code": e.code, "message": f"HTTP {e.code}: {text}", "ticket_id": None}
    except TimeoutError:
        return {"code": -4, "message": "请求超时，工单可能已创建，请勿直接重试", "ticket_id": None}
    except URLError as e:
        if isinstance(e.reason, TimeoutError):
            return {"code": -4, "message": "请求超时，工单可能已创建，请勿直接重试", "ticket_id": None}
        return {"code": -2, "message": f"网络错误: {e.reason}", "ticket_id": None}
    except Exception as e:
        return {"code": -3, "message": f"未知错误: {e}", "ticket_id": None}


# ============================================================
# 创建工单
# ============================================================

def create_gdex_ticket(name, phone, address, appointment_time):
    """
    调用 Udesk 接口创建上门工单。

    Args:
        name:             客户姓名（必填）
        phone:            联系电话（必填）
        address:          预约安装地点（必填，客户原话）
        appointment_time: 预约日期（必填，必须为 YYYY-MM-DD 格式）

    Returns:
        dict: 包含 code、message、ticket_id（失败时可能带 hint）
    """
    name = str(name or "").strip()
    if not name:
        return {"code": -1, "message": "客户姓名不能为空", "ticket_id": None}
    phone, err = normalize_phone(phone)
    if err:
        return {"code": -1, "message": err, "ticket_id": None}
    address = str(address or "").strip()
    if not address:
        return {"code": -1, "message": "预约安装地点不能为空", "ticket_id": None}
    appointment_time = str(appointment_time or "").strip()
    if not appointment_time:
        return {"code": -1, "message": "预约时间不能为空", "ticket_id": None}
    # Udesk 服务端校验该字段必须为 YYYY-MM-DD（否则返回 7001），本地先拦截
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", appointment_time):
        return {"code": -1,
                "message": f"预约时间格式不正确：{appointment_time}，必须为 YYYY-MM-DD（如 2026-10-30）",
                "ticket_id": None}

    # 防呆：模板未配置时不建单，避免 Udesk 静默降级到默认模板导致两个字段全部丢失
    if not TEMPLATE_ID:
        return {"code": -1,
                "message": "工单模板未配置（TEMPLATE_ID=0），已阻止建单",
                "ticket_id": None}

    ticket_data = {
        "subject": TICKET_SUBJECT,
        "content": TICKET_CONTENT,
        "status_id": 1,  # 开启
        "template_id": TEMPLATE_ID,
        "ticket_field": {
            FIELD_NAME: name,
            FIELD_PHONE: phone,
            FIELD_ADDRESS: address,
            FIELD_TIME: appointment_time,
        },
    }
    for key, val in (("assignee_email", ASSIGNEE_EMAIL),
                     ("agent_group_name", AGENT_GROUP_NAME),
                     ("priority", PRIORITY)):
        if val:
            ticket_data[key] = val

    payload = json.dumps({"ticket": ticket_data}, ensure_ascii=False).encode("utf-8")

    result = _send(payload, "sha256")
    if result["code"] == 2059:  # 签名不对：改用 SHA1 重试（鉴权失败时不会创建工单，重试安全）
        result = _send(payload, "sha1")

    if result["code"] != 1000 and result["code"] in HINTS:
        result["hint"] = HINTS[result["code"]]
    return result

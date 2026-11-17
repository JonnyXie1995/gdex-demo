# GDEX-demo — Udesk 上门安装工单技能

一个 WorkBuddy / 平台函数技能：客户预约上门安装时，把预约信息登记为一张真实的 Udesk 工单。

工单字段固定，四项业务信息（姓名、联系电话、安装地点、预约时间）作为变量写入自定义字段。

## 功能

| 项目 | 值 |
|---|---|
| 工单标题 | `onsite installation`（固定） |
| 工单内容 | `IM-onsite installation`（固定） |
| 工单模板 | `3195`（GDEX-ticket） |
| 客户姓名 | `TextField_2557`（Name） |
| 联系电话 | `TextField_6709`（Phone Number） |
| 预约安装地点 | `TextField_3783`（address） |
| 预约时间 | `TextField_2563`（Expected delivery date，`YYYY-MM-DD`） |
| 状态 | 开启 |
| 客户关联 | 不关联客户 |

## 目录结构

```
.
├── SKILL.md                 技能定义（含调用时机、话术、返回值处理）
├── CHANGELOG.md             版本变更记录
├── scripts/
│   └── create_ticket.py     核心实现：create_gdex_ticket()
├── tests/
│   └── test_local.py        本地回归测试（21 项，不联网）
└── docs/
    └── TEST-REPORT.md       实测报告
```

## 快速开始

### 1. 配置

打开 `scripts/create_ticket.py`，填写脚本顶部的常量：

```python
API_BASE_URL   = "https://<你的子域名>.udesk.cn"
ADMIN_EMAIL    = "<超级管理员邮箱>"
OPEN_API_TOKEN = "<API Token>"     # 本仓库中已脱敏为 ""
```

Token 获取路径：Udesk 管理后台 → 设置 → 安全设置 → API Token。
**该文件已加入 `.gitignore` 白名单机制，提交前请务必确认没有把真实 token 写进版本库。**

如果工单需要自动分派，再填 `ASSIGNEE_EMAIL` / `AGENT_GROUP_NAME` / `PRIORITY`，留空则由 Udesk 自身规则处理。

### 2. 注册为平台函数

把 `scripts/create_ticket.py` 里的 `create_gdex_ticket` 按平台既有方式注册为函数：

```python
create_gdex_ticket(name, phone, address, appointment_time)
```

| 参数 | 说明 |
|---|---|
| `name` | 客户姓名，必填，使用客户自己说出的姓名 |
| `phone` | 联系电话，必填；空格、横线、括号、`+86`、`0086` 会被自动整理 |
| `address` | 预约安装地点，必填，使用客户原话，不要改写或缩写 |
| `appointment_time` | 预约日期，必填，**必须为 `YYYY-MM-DD`** |

返回 `{"code", "message", "ticket_id"}`，失败时可能多一个 `hint`。

| 返回 | 含义 | 处理 |
|---|---|---|
| `code == 1000` 且 `ticket_id` 非空 | 创建成功 | 记录 `ticket_id` 并告知客户 |
| `code == -1` | 参数不合法（`message` 指明哪一项） | 补问或更正后重试 |
| `code == -4` | 请求超时，工单可能已创建 | **不要重试**，转人工 |
| `code == -2` / `-3` / `20623` | 网络/未知错误/nonce 重复 | 最多重试 1 次 |
| 其他 | 鉴权或配置问题（见 `hint`） | **不要重试**，转人工 |

## 测试

```bash
python tests/test_local.py
```

覆盖电话号码清洗、四项参数校验、日期格式拦截、模板防呆，共 21 项，**不发起任何网络请求**，可安全在 CI 中运行。

真实建单的验证方法见 `docs/TEST-REPORT.md`。

## 设计要点

- **本地先校验**：姓名/电话/地点/时间与日期格式都在本地拦截，不消耗接口配额
- **模板防呆**：`TEMPLATE_ID = 0` 时直接拒绝建单——模板 ID 写错时 Udesk 会静默降级到默认模板，导致姓名和电话丢失但接口仍返回成功
- **签名规范**：`SHA256(email&token&timestamp&nonce&sign_version)`，官方要求 SHA256 失败时改用 SHA1，脚本已内置自动降级
- **错误码语义化**：`HINTS` 表把 Udesk 错误码翻译为可操作的提示，供 agent 判断是否重试

## 环境限制

- 接口频次：**60 次/分钟**
- 运行环境时间与服务器相差超过 **5 分钟**会被拒绝（`code 20622`）
- `nonce` 15 分钟内只能使用一次（`code 20623`）

## 安全

- 仓库内 **不含任何真实 token**，`OPEN_API_TOKEN` 为空占位符
- 请勿把填好 token 的脚本提交到公开仓库
- 建议为该系统单独创建专用 API 账号与低权限 token，不要复用超级管理员全权限 token

## 版本

当前 `v4.0.1`，详见 [CHANGELOG.md](CHANGELOG.md)。

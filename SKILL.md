---
name: GDEX-demo
description: 创建 Udesk 上门工单。当客户预约上门安装，并且已收集到姓名、联系电话、安装地点、预约时间四项信息、且已向客户复述并获得确认后，调用本
  skill 创建工单。工单标题和内容为固定值，四个业务字段是变量。
---
# 创建上门工单

## 用途

客户预约上门安装时，用一张真实的 Udesk 工单登记预约。工单会记录客户姓名、联系电话、安装地点和预约时间，工作人员会根据工单里的信息另行联系客户确认。

## 调用时机

- 只在姓名、联系电话、安装地点、预约时间四项都已收集到，并且已向客户复述、客户明确确认之后调用。复述确认的流程由提示词的"场景 B"负责。
- 任何一项缺失、或客户尚未确认时，不要调用；先补问缺失项。
- 不得编造任何一项信息；客户拒绝提供时，不得用假信息代替。
- 如果本次对话里，相同信息已经成功创建过工单，直接告知已有工单号，不要再次创建。客户确实提出新的预约，才创建新工单。

## 调用的函数

```python
create_gdex_ticket(name=name, phone=phone, address=address, appointment_time=appointment_time)
```

| 参数 | 说明 |
|---|---|
| name | 客户姓名，必填，使用客户自己说出的姓名 |
| phone | 联系电话，必填。空格、横线、+86 会被自动整理；格式不对会返回 code -1 |
| address | 预约安装地点，必填，使用客户原话（含门店名/详细地址），不要改写或缩写 |
| appointment_time | 预约日期，必填，**必须为 YYYY-MM-DD 格式**（如 2026-10-30）。客户说"明天""下周三"等相对日期时，必须先和客户确认具体日期再换算；客户提到的时间段（上午/下午）无法写入该字段，向客户说明具体上门时间段由工作人员联系确认 |

## 工单内容（固定）

| 项目 | 值 |
|---|---|
| 标题 | onsite installation |
| 内容 | IM-onsite installation |
| 模板 ID | 3195（GDEX-ticket） |
| 客户姓名 | 写入自定义字段 TextField_2557（Name） |
| 联系电话 | 写入自定义字段 TextField_6709（Phone Number） |
| 预约安装地点 | 写入自定义字段 TextField_3783（address） |
| 预约时间 | 写入自定义字段 TextField_2563（Expected delivery date） |
| 状态 | 开启 |
| 客户关联 | 不关联客户 |

四项业务信息只出现在上面四个自定义字段里。

## 返回值处理

函数返回 `{"code", "message", "ticket_id"}`，失败时可能多一个 `hint`。

| 返回 | 含义 | 处理 |
|---|---|---|
| `code == 1000` 且 `ticket_id` 非空 | 创建成功 | 记住 `ticket_id`，按下面的话术告知客户 |
| `code == -1` | 某项信息不合法（message 会指明是哪一项） | 向客户补问或更正对应信息，重新复述确认后再调用 |
| `code == -4` | 请求超时，工单可能已创建 | **不要重试**。按提示词转人工 |
| `code == -2` / `-3` / `20623` | 网络、未知错误或 nonce 重复 | 最多重试 1 次；仍失败则按提示词转人工 |
| 其他 | 鉴权或配置问题（见 `hint`） | **不要重试**，按提示词转人工 |

- 失败时如实告知暂时无法提交，不要编造工单号。
- 不要把 `message`、`hint` 的内容转述给客户，也不要暴露内部参数或错误码。

## 对客户的话术

成功后，按客户使用的语言回复，包含工单号：

- EN: "Your request has been registered. Your reference number is {ticket_id}. Our team will call you at the number you provided to confirm the visit time."
- 中文："您的预约已登记，工单号为 {ticket_id}。工作人员会按您提供的电话联系确认上门时间。"
- MS: "Permintaan anda telah direkodkan. Nombor rujukan anda ialah {ticket_id}. Pasukan kami akan menghubungi anda melalui nombor yang diberikan untuk mengesahkan masa lawatan."

不要承诺具体的上门时间，也不要声称已经安排了工程师。

## 平台配置

- 按现有平台脚本的方式，把 `scripts/create_ticket.py` 里的 `create_gdex_ticket` 注册为平台函数。
- 没有命令行入口，不读环境变量，也没有配置文件。配置全部写在脚本顶部的常量里：接口地址、管理员邮箱、token、模板 ID、四个字段 key。
- 当前环境：`https://udesk-wofeng.s5.udesk.cn`，模板 `3195`（GDEX-ticket）。
- 模板 ID 被设为 `0` 时，函数会直接返回 `code -1` 拒绝建单——这是防呆：模板 ID 写错时 Udesk 会静默降级到默认模板，导致姓名和电话全部丢失但接口仍返回成功。
- 如需自动分派，在脚本顶部填写 `ASSIGNEE_EMAIL`、`AGENT_GROUP_NAME`、`PRIORITY`，留空则由 Udesk 自身规则分派。
- 接口限制：每分钟最多 60 次；运行环境时间与服务器相差超过 5 分钟会被拒绝。
- 脚本里包含真实 token，请勿上传到公开仓库或分享给无关人员。
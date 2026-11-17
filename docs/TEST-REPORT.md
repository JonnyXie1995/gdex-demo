# 测试报告

测试时间：2026-11-17
被测版本：v4.0.0 脚本 / v4.0.1 打包
环境：`https://udesk-wofeng.s5.udesk.cn`（演示环境），模板 `3195`

## 1. 本地回归测试

`python tests/test_local.py` → **21 passed, 0 failed**

| 分组 | 项数 | 结果 | 覆盖内容 |
|---|---|---|---|
| 电话号码清洗 | 9 | 全通过 | 横线/空格/括号/`+86`/`0086`/`86` 前缀、座机、国际号码、非法输入、空值 |
| 参数校验 | 11 | 全通过 | 姓名空/空格/None、电话空/格式错、地址空、时间空、三种非法日期格式 |
| 模板防呆 | 1 | 通过 | `TEMPLATE_ID=0` 时本地拒绝建单 |

全部为本地断言，不发起网络请求。

## 2. 真实建单（端到端）

调用：

```python
create_gdex_ticket(
    name="API-测试-v4-请删除",
    phone="138 0013 8000",
    address="测试地址：北京市朝阳区测试路1号（v4联调）",
    appointment_time="2026-11-21",
)
```

返回：`{"code": 1000, "message": "工单创建成功", "ticket_id": 21584091}`

读回校验（`GET /open_api_v1/tickets`）：

| 校验项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| `template_id` | 3195 | 3195 | ✅ 未发生模板静默降级 |
| `subject` / `content` | onsite installation / IM-onsite installation | 一致 | ✅ |
| `status` | 开启 | 开启 | ✅ |
| 姓名 `TextField_2557` | 原样 | `API-测试-v4-请删除` | ✅ |
| 电话 `TextField_6709` | 归一化 | `13800138000`（输入为 `138 0013 8000`） | ✅ |
| 地址 `TextField_3783` | 原样（未改写） | 与输入一致 | ✅ |
| 预约时间 `TextField_2563` | `YYYY-MM-DD` | `2026-11-21` | ✅ |

## 3. 签名算法验证

按官方文档 `sign = SHA256(email&open_api_token&timestamp&nonce&sign_version)`，脚本实现一致。

测试过程中确认的两点：

- 服务端在 **nonce 复用** 时会先返回 `20623`，因此在做签名排查时必须每次使用全新 nonce，否则结果不可信
- `2059`（签名错误）在正常 token 下可通过自动降级到 SHA1 恢复；若两种算法均失败，则应优先怀疑 token 失效而非算法错误

## 4. 已知问题

- `GET /open_api_v1/tickets/:id`（单票详情）返回 404，读取单张工单需通过列表接口定位
- 列表接口 `meta.total_pages` 按 `per_page=5` 计算，实际使用其他 `per_page` 时需自行换算末页

## 5. 测试数据清理

测试在演示环境创建了真实工单（`21583955`、`21584091`），验证完成后应在后台删除。

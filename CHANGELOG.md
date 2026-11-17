# CHANGELOG

遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## v4.0.1 — 2026-11-17

开源打包整理，功能无变化。

- **安全**：`OPEN_API_TOKEN` 脱敏为空占位符，仓库内不保留任何真实 token
- **文档**：`SKILL.md` 的 `description` 修正为"四项信息"触发条件，与正文调用时机、参数表、脚本校验保持一致
- **新增**：README、测试报告、本地回归测试脚本
- **测试**：本地 21 项回归全通过；真实建单 `code 1000`，四个自定义字段读回校验通过

## v4.0.0 — 2026-11-17

- **修复**：更换失效的 API Token，恢复建单能力
- 其余同 v3.0.0

## v3.0.0 — 2026-11-17

- **新增**：预约安装地点 → `TextField_3783`（address）
- **新增**：预约时间 → `TextField_2563`（Expected delivery date，服务端强制 `YYYY-MM-DD`）
- **变更**：联系电话字段 `TextField_2556` → `TextField_6709`（Phone Number）
- **变更**：模板改为 `3195`（GDEX-ticket），工单字段从 2 个扩展为 4 个
- 测试：本地 21 项通过；真实建单 `code 1000`，字段读回校验通过

## v2.x — 更早

- 切换到 Udesk wofeng 演示环境；平台函数更名为 `create_gdex_ticket`，避免与其他技能的 `create_ticket` 重名

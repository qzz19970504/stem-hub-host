# 透传协议实机验收记录（2026-08-21）

## 测试环境

- 上位机分支：`codex/transparent-mode-9600`
- MCU 固件版本握手：`release-v3.2`
- UART1（MCU 命令口）：COM12，FTDI，9600 8N1
- 当前下游串口：COM10，CH340，实测连接 MCU UART2，9600 8N1
- 固件仓库未作修改；原有两个 `.settings/*.json` 未提交改动保持不变

## 自动实机冒烟

执行：

```powershell
& 'env\release\Scripts\python.exe' tools\real_serial_smoke.py `
  --port COM12 --downstream-port COM10 --target uart2 --duration-seconds 5
```

结果：通过。

- `AT+VERSION?` 握手成功，版本满足 `release-v3.2`
- `AT+SENSE?`、`AT+FAULT?`、`AT+MOTOR?` 均收到有效响应
- `AT+TRANS=1` 成功进入 UART2 独占透传
- 正向原始数据完整一致：
  `484F53542D5452414E5300FF6162632B2B2B646566`
- 反向原始数据经 `+UART2RX` 完整恢复：
  `4D43552D5452414E5300FF`
- 正向数据中的嵌入式 `+++` 正常透传，没有触发退出
- 受保护的独立 `+++` 成功退出，随后 `AT+SENSE?` 成功，证明已恢复 AT 模式
- 测试结束时安全关闭串口，未留下透传会话

## 范围说明

当前物理接线验证的是 UART2。UART3 曾按原接线假设尝试，但 COM10 未收到
UART3 数据；进一步探测确认 COM10 实际连接 UART2。因此本记录不宣称 UART3
实机通过。UART3 与双路模式由自动化假固件测试覆盖，待对应硬件接线具备后再补
实机验收。

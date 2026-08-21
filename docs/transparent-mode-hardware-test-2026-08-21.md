# 透传协议实机验收记录（2026-08-21）

## 测试环境

- 上位机分支：`codex/transparent-mode-9600`
- MCU 固件版本握手：`release-v3.2`
- UART1（MCU 命令口）：COM12，FTDI，9600 8N1
- 下游串口：COM10，CH340，分别改接 MCU UART2、UART3，9600 8N1
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

首次测试时 COM10 实际连接 UART2，完成了上述 UART2 验收。随后将 COM10 改接
MCU UART3，并执行：

```powershell
& 'env\release\Scripts\python.exe' tools\real_serial_smoke.py `
  --port COM12 --downstream-port COM10 --target uart3 --duration-seconds 5
```

UART3 结果同样通过：

- `AT+TRANS=2` 成功进入 UART3 独占透传
- 正向原始数据完整一致：
  `484F53542D5452414E5300FF6162632B2B2B646566`
- 反向原始数据经 `+UART3RX` 完整恢复：
  `4D43552D5452414E5300FF`
- 嵌入式 `+++`、受保护退出及退出后的 `AT+SENSE?` 全部通过
- 无意外断线、握手失败、串口错误或替换字符

UART2 和 UART3 均已分别实机验证。双路目标由自动化假固件测试覆盖，本次未进行
双下游物理接线测试。最后一次 UART3 测试结束时已退出透传并安全关闭串口。

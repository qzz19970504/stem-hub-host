# Bidirectional UART tunnel and firmware contract design

One protocol contract aligns the PySide6 host with the STM32 firmware and adds
binary-safe, source-aware replies from UART2 and UART3.

- Module: serial protocol and passthrough
- Status: Approved design
- Scope: `stem-hub-host` and sibling firmware repository `stem-hub`
- Firmware source baseline: `9605dbd8116ee6829e027250cfa0a3b093c6fa46`
- Host source baseline: `18e7e4cabb37132473dd0ba03446d2ac4930cffd`

## User story

As an operator, I want the host and firmware to share one exact command
contract and carry replies from downstream UART devices in both text and Hex
forms, so that device errors and arbitrary binary payloads are visible without
losing control of the STM32 AT channel.

## Source audit

The audit uses firmware implementation and tests only. Firmware README and
documentation files are not protocol authorities.

The following existing commands already match exactly, including uppercase
spelling, `ON`/`OFF` values, and terminal `\r\n`:

| Capability | Request |
| --- | --- |
| Handshake | `AT+VERSION?\r\n` |
| Telemetry | `AT+SENSE?\r\n` |
| Faults | `AT+FAULT?\r\n` |
| Motor state | `AT+MOTOR?\r\n` |
| Diagnostics | `AT+DIAG?\r\n` |
| Motor control | `AT+MOTOR=SLEEP|WAKE|FWD|REV|BRAKE|STOP\r\n` |
| Light master | `AT+LED=ON|OFF\r\n` |
| Auxiliary outputs | `AT+NMOS1=ON|OFF\r\n`, `AT+NMOS2=ON|OFF\r\n` |
| Charging path | `AT+LM51770=ON|OFF\r\n` |
| Discharging path | `AT+MP4317=ON|OFF\r\n` |
| UART2 bridge | `AT+UART2=ON|OFF\r\n` |
| UART3 bridge | `AT+UART3=ON|OFF\r\n` |
| Dual bridge | `AT+UART2&3=ON|OFF\r\n` |

The existing charging transition is retained:

- Charge: MP4317 off, LM51770 off, LM51770 on.
- Discharge: LM51770 off, MP4317 off, MP4317 on.
- Each command is queued only after the previous firmware `OK`.

Two source-level mismatches require changes:

1. The host diagnostic model contains the removed `UART_WDG` field but omits
   the firmware's current TX-state and sensor-lifecycle fields.
2. The host advertises bidirectional raw passthrough while the firmware only
   forwards CRLF-delimited UART1 text to UART2/3. UART2/3 receive interrupts and
   return framing do not exist, and `strlen` makes embedded zero bytes unsafe.

## Selected architecture

Use the existing UART1 AT channel as a framed binary tunnel. Do not switch
UART1 into an ambiguous raw mode and do not use a `+++` escape sequence.

This keeps AT control available at all times, preserves arbitrary payload
bytes, identifies the source UART, and lets AT responses and downstream data
share one deterministic line parser.

### Host-to-firmware payload

```
AT+UARTTX=<HEX>\r\n
```

Rules:

- `<HEX>` contains 2 through 64 uppercase hexadecimal characters, representing
  1 through 32 payload bytes.
- The UI accepts uppercase or lowercase Hex input, but host-generated commands,
  firmware parsing, and firmware events use uppercase.
- Separators, whitespace, odd digit counts, and non-hex characters are invalid.
- The firmware AT protocol line limit increases from 48 to 96 bytes, remaining
  below the existing 128-byte UART1 line buffer.
- At least one of the existing UART2/UART3 bridge flags must be enabled.
- The decoded bytes are transmitted unchanged to every enabled target.
- The command returns `OK\r\n` only after all selected UART transmissions
  succeed.
- Errors are `ERROR:HEX`, `ERROR:UART_DISABLED`, or `ERROR:UART_TX`.

Long host payloads are split into ordered 32-byte commands. The next chunk is
not sent until the preceding chunk receives `OK`, so FIFO order and failure
attribution remain deterministic.

### Firmware-to-host payload

```
+UART2RX:<HEX>\r\n
+UART3RX:<HEX>\r\n
```

Rules:

- Each event contains 1 through 32 payload bytes encoded as uppercase Hex
  without separators.
- The source prefix is mandatory even when only one bridge is enabled.
- RX events are out-of-band and may arrive before, between, or after a pending
  command's data and terminal response.
- The host must route these frames to the passthrough panel without consuming
  or completing the pending AT-command FIFO entry.
- RX byte counters count decoded payload bytes, not framing overhead.

### Text and Hex UI semantics

- Text transmit encodes UTF-8 and appends CRLF when absent.
- Hex transmit sends exactly the entered bytes and does not append CRLF.
- Text receive shows a timestamp and `[UART2]` or `[UART3]` source tag.
- Hex receive shows the same source tag followed by decoded payload bytes.
- A queued transmit clears the editor. Confirmed TX count advances per
  acknowledged payload chunk. If a later chunk fails, unsent chunks are
  discarded and the terminal reports both the error and confirmed byte count.

## Firmware components

### Protocol parser

`AppAtCommand` gains a UART payload command with a fixed 32-byte array and
explicit length. Parsing validates the complete Hex body before returning a
command. The existing command spellings and aliases remain unchanged.

### Binary-safe transmit

Add a length-based runtime transmit function. `App_RuntimeSendText` delegates
to it for text, while `AT+UARTTX` uses it directly for UART2/3 payloads.
Embedded zero bytes must never pass through `strlen`.

### UART2/3 receive

- Arm one-byte interrupt receive on UART2 and UART3 during runtime
  initialization.
- ISR callbacks only push bytes into dedicated ring buffers, update counters,
  release a semaphore, and re-arm receive.
- A new bridge task drains each enabled source in chunks of at most 32 bytes,
  Hex-encodes them, and sends source-aware events on UART1.
- No HAL transmit or string formatting occurs inside an ISR.
- Disabling a bridge flushes that source's pending RX bytes so stale data is
  not emitted after a later re-enable.

### UART1 serialization

All normal task-level UART1 writes use one mutex so AT replies and asynchronous
UART RX events cannot interleave at byte level. Failure-record polling output
remains independent because it is used outside normal task execution.

### Diagnostics

The firmware retains its current DIAG fields and adds:

- `UART2_RX_BYTE`
- `UART2_RX_OVERFLOW`
- `UART3_RX_BYTE`
- `UART3_RX_OVERFLOW`

The host model mirrors all current firmware fields:

- RX ISR/error counters
- line and AT loop counters
- TX call/OK/timeout/error/busy counters
- TX state/error snapshots and last status
- sensor loop/publish/read-failure counters
- UART2/3 RX byte/overflow counters

The obsolete `UART_WDG` value remains accepted as an optional legacy field but
is no longer emitted by the fake firmware or treated as current contract data.

## Host components

- `at_protocol.py` builds chunked `AT+UARTTX` commands and parses source-aware
  RX events.
- `SerialWorker` keeps CRLF parsing active in bridge mode and routes RX events
  before pending-command attribution.
- `Controller` owns the ordered chunk queue, pauses telemetry polling while a
  bridge is active, and emits confirmed-byte and failure signals.
- `PassthroughPanel` applies the text/Hex semantics above and renders UART
  source tags.
- `FakeFirmware` implements the same tunnel, current diagnostics, and error
  responses for end-to-end host tests.

## Error and recovery behavior

- A malformed tunnel command does not alter bridge state or transmit bytes.
- A UART TX failure stops the current host payload; later chunks are not sent.
- A bridge mode change waits for its AT acknowledgement before accepting
  payload data.
- Closing or timing out the serial connection clears pending tunnel chunks,
  pending RX parser state, and visible active-bridge state.
- Turning a bridge off remains possible because UART1 never leaves AT framing.

## Acceptance criteria

- [ ] Every existing host-generated command is accepted by the firmware parser
      with exact spelling and CRLF framing.
- [ ] Every firmware query data line is parsed into the corresponding host
      model using current field names.
- [ ] Binary payloads containing `00`, `0D 0A`, `FF`, and invalid UTF-8 bytes
      round-trip without mutation.
- [ ] Payloads longer than 32 bytes are ordered and acknowledged chunk by
      chunk.
- [ ] UART2 and UART3 replies remain distinguishable in both text and Hex view.
- [ ] RX events cannot complete or corrupt an unrelated pending AT command.
- [ ] Disabled bridges neither transmit payloads nor surface stale RX bytes.
- [ ] Charge/discharge ordering and all existing control behaviors remain
      unchanged.
- [ ] Firmware parser/runtime tests, host unit/integration tests, and visual
      regression tests pass.
- [ ] The STM32 firmware builds from source.
- [ ] The retained `env/release` environment rebuilds
      `dist/stem-hub-host.exe`, and the packaged app passes a `--fake` smoke
      launch.

## Standards checklist

- [x] Firmware implementation, not documentation, is the protocol authority.
- [x] Existing commands remain backward compatible.
- [x] Binary data uses explicit lengths rather than C string termination.
- [x] ISR work is bounded and non-blocking.
- [x] Shared UART1 transmission is serialized.
- [x] New behavior is testable without physical hardware.
- [x] No unrelated UI, sensor, motor, or power-path refactor is included.
- [x] The retained release environment is preserved.

## Open questions

None. The operator selected the framed binary tunnel, 32-byte chunks, exact
Hex transmission, text CRLF convenience, and changes to both repositories.

## Related features

- Existing serial handshake and FIFO response attribution
- Existing mutually exclusive UART bridge selector
- Existing charge/discharge break-before-make controller
- Existing fake firmware and PyInstaller release flow

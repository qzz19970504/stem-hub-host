# Bidirectional UART Tunnel Firmware Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the PySide6 host and STM32 firmware share one verified, binary-safe, bidirectional UART2/UART3 tunnel contract, then rebuild both deliverables.

**Architecture:** Keep the existing AT command channel on USART1 and carry binary tunnel data as hexadecimal AT frames. Host-to-device data uses `AT+UARTTX=<HEX>` and device-to-host data uses unsolicited `+UART2RX:<HEX>` / `+UART3RX:<HEX>` events. Firmware interrupt handlers only enqueue received bytes; task context handles framing, transmission, and diagnostic counters. The host keeps its line parser active, routes unsolicited tunnel events outside the pending-command FIFO, and serializes payload chunks through normal command acknowledgements.

**Tech Stack:** STM32 HAL/FreeRTOS/C11, PySide6/Python 3.11, pytest, MinGW native firmware protocol tests, CMake/Ninja/arm-none-eabi-gcc, PyInstaller.

**Status:** Implemented and verified on 2026-07-26. The retained checkboxes below describe the original execution sequence; final evidence is recorded in the repository commits and build artifacts.

---

## File map

### Firmware: `D:\Codes\STM32\stem-hub`

- `App/Inc/app_at_protocol.h`: parsed UART payload command model.
- `App/Src/app_at_protocol.c`: strict `AT+UARTTX=<HEX>` parser and validation.
- `App/Inc/app_config.h`: AT line and tunnel chunk limits.
- `App/Inc/app_runtime.h`, `App/Src/app_runtime.c`: UART1 serialized TX, UART2/3 RX rings, callbacks, diagnostics.
- `App/Inc/app_uart_tunnel.h`, `App/Src/app_uart_tunnel.c`: pure hex encode/decode helpers.
- `App/Inc/app_bridge.h`, `App/Src/app_bridge_task.c`: drain UART2/3 rings and emit unsolicited frames.
- `App/Src/app_at_task.c`: execute binary UART sends and return precise errors.
- `App/Inc/app_types.h`, `App/Src/app_state.c`: current bridge state and expanded diagnostics.
- `Core/Src/freertos.c`: create the bridge task.
- `cmake/stm32cubemx/CMakeLists.txt`: compile new firmware sources.
- `tests/test_at_protocol.c`, `tests/test_uart_tunnel.c`: native protocol regression tests.

### Host: `D:\Codes\STM32\stem-hub-host`

- `stem_hub_host/at_protocol.py`: UART TX command construction and unsolicited RX parsing.
- `stem_hub_host/models.py`: current firmware diagnostics and typed UART RX events.
- `stem_hub_host/serial_worker.py`: keep line parsing enabled and route unsolicited frames independently.
- `stem_hub_host/controller.py`: 32-byte chunk queue, ACK sequencing, failure handling, source-tagged RX.
- `stem_hub_host/fake_firmware.py`: emulate the new contract and current diagnostics.
- `stem_hub_host/ui/widgets/passthrough_panel.py`: exact Hex transmission and case-insensitive parsing.
- `tests/test_at_protocol.py`, `tests/test_behavior_regressions.py`: host-side contract and behavior tests.

## Task 1: Lock down the firmware parser contract

- [ ] Add failing cases to `tests/test_at_protocol.c` for:
  - `AT+UARTTX=00FF10` decoding to three exact bytes.
  - empty, odd-length, lowercase, non-hex, and over-32-byte payload rejection.
  - maximum command length accepting 64 hex digits.
- [ ] Compile and run the native parser test to verify the new assertions fail:

```powershell
& 'D:\Toolchains\MinGW\bin\gcc.exe' -std=c11 -Wall -Wextra -Werror `
  -I 'D:\Codes\STM32\stem-hub\App\Inc' `
  'D:\Codes\STM32\stem-hub\tests\test_at_protocol.c' `
  'D:\Codes\STM32\stem-hub\App\Src\app_at_protocol.c' `
  -o 'D:\Codes\STM32\stem-hub-host\build\contract-tests\test_at_protocol.exe'
& 'D:\Codes\STM32\stem-hub-host\build\contract-tests\test_at_protocol.exe'
```

- [ ] Add `APP_AT_COMMAND_SEND_UART`, a fixed `uint8_t uart_payload[32]`, and `uart_payload_length` to `app_at_protocol.h`.
- [ ] Implement strict uppercase hex parsing in `app_at_protocol.c`; distinguish syntax errors from valid commands and raise the AT line limit to 96 bytes.
- [ ] Recompile and run the parser test until it passes.
- [ ] Commit the parser contract changes.

## Task 2: Implement and test pure tunnel framing

- [ ] Create `tests/test_uart_tunnel.c` with failing tests for:
  - encoding byte arrays including `0x00` and `0xFF`;
  - producing `+UART2RX:<HEX>\r\n` and `+UART3RX:<HEX>\r\n`;
  - rejecting destination buffers that cannot hold the complete frame.
- [ ] Compile the test against the not-yet-created helper and confirm failure.
- [ ] Add `app_uart_tunnel.h/.c` with interfaces:

```c
bool App_UartTunnelEncodeEvent(
    uint8_t uart_index,
    const uint8_t *payload,
    size_t payload_length,
    char *destination,
    size_t destination_capacity,
    size_t *encoded_length);
```

- [ ] Run both native firmware tests and confirm they pass with warnings treated as errors.
- [ ] Commit the framing helper and tests.

## Task 3: Add firmware binary TX and UART2/UART3 RX plumbing

- [ ] Add focused tests or compile-time seams for ring overflow, exact-byte preservation, and bridge-disabled flushing.
- [ ] Extend runtime state with:
  - one-byte interrupt receive slots for USART2 and USART3;
  - bounded RX rings and a bridge semaphore;
  - a mutex serializing all USART1 task-context output;
  - `UART2_RX_BYTE`, `UART2_RX_OVERFLOW`, `UART3_RX_BYTE`, and `UART3_RX_OVERFLOW` counters.
- [ ] Update `HAL_UART_RxCpltCallback` and UART error recovery to re-arm all three UARTs without transmitting or formatting inside an ISR.
- [ ] Add an exact-length runtime transmit API:

```c
HAL_StatusTypeDef App_RuntimeSendBytes(
    UART_HandleTypeDef *uart,
    const uint8_t *data,
    uint16_t length,
    uint32_t timeout);
```

- [ ] Keep `App_RuntimeSendText` as a wrapper and route all USART1 responses/events through the TX mutex.
- [ ] Verify native tests and compile affected firmware sources with the ARM toolchain.
- [ ] Commit the runtime changes.

## Task 4: Execute the firmware tunnel commands and events

- [ ] Add firmware task-level tests covering:
  - `ERROR:UART_DISABLED` when neither bridge is enabled;
  - exact bytes sent to each enabled UART;
  - `ERROR:UART_TX` on any selected target failure;
  - `OK` only after all selected targets succeed;
  - RX buffers flushed when a bridge is turned off.
- [ ] Handle `APP_AT_COMMAND_SEND_UART` in `app_at_task.c`.
- [ ] Add `app_bridge_task.c` to drain each RX ring in chunks of at most 32 bytes and emit `+UART2RX` / `+UART3RX` events.
- [ ] Register the bridge task in `freertos.c` and the new source files in the CMake target.
- [ ] Extend `AT+DIAG?` output with the four UART RX counters while preserving existing field names.
- [ ] Run firmware native tests and a full Debug firmware build.
- [ ] Commit the operational tunnel.

## Task 5: Lock down the host protocol model

- [ ] Add failing pytest cases for:
  - splitting payloads into 32-byte uppercase-hex `AT+UARTTX` commands;
  - preserving `0x00`, CR, LF, and `0xFF`;
  - parsing both unsolicited UART RX event forms;
  - rejecting malformed or oversized event payloads;
  - parsing every current firmware diagnostic field without inventing `UART_WDG`.
- [ ] Run the focused tests and confirm failure:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' `
  -m pytest tests/test_at_protocol.py -q
```

- [ ] Add typed UART RX events and current diagnostics to `models.py`.
- [ ] Add chunk construction and event parsing to `at_protocol.py`.
- [ ] Rerun the focused tests until they pass.
- [ ] Commit the host protocol model.

## Task 6: Replace raw passthrough with acknowledged AT framing

- [ ] Add failing behavior tests proving:
  - unsolicited UART events never resolve or shift the pending-command FIFO;
  - one payload chunk is in flight at a time;
  - the next chunk is sent only after `OK`;
  - errors stop the queue and identify the failed payload;
  - text mode adds CRLF only when absent;
  - Hex mode adds no bytes and accepts lowercase input.
- [ ] Run the focused behavior tests and confirm failure.
- [ ] Keep `SerialWorker` line parsing enabled in every bridge mode and emit a dedicated signal for parsed UART RX events.
- [ ] Replace controller raw writes with a 32-byte command queue using normal AT acknowledgements.
- [ ] Route RX events to the UI with `[UART2]` / `[UART3]` source tags.
- [ ] Remove obsolete raw-mode toggling while retaining telemetry pause/resume and bridge mutual exclusion.
- [ ] Update the passthrough panel and fake firmware to match the real contract and diagnostics.
- [ ] Run focused tests until they pass.
- [ ] Commit the host behavior changes.

## Task 7: Cross-contract verification and rebuilding

- [ ] Run all native firmware tests with `-Wall -Wextra -Werror`.
- [ ] Locate the STM32 bundled CMake, Ninja, and GNU Arm toolchain and build the firmware Debug preset from a clean build directory.
- [ ] Run the complete host test suite:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests -q
```

- [ ] Run the visual regression suite and confirm all baselines pass.
- [ ] Rebuild `dist\stem-hub-host.exe` using the preserved `env\release` environment.
- [ ] Launch the packaged program with `--fake`, keep it alive for at least three seconds, and close it cleanly.
- [ ] Inspect final repository status, confirm no generated build folders are accidentally staged, and commit the verified cross-repository implementation.

## Task 8: Self-review and handoff

- [ ] Compare implementation against every command, error, chunk, ordering, and diagnostic requirement in the approved design spec.
- [ ] Search changed source and tests for `TODO`, `FIXME`, placeholder assertions, obsolete raw passthrough, and active use of `UART_WDG`.
- [ ] Record fresh test counts, firmware artifact path, host EXE path/size, and both commit hashes.
- [ ] Report any optional toolchain warnings separately from functional failures.

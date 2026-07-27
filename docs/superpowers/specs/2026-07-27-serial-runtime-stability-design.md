# Serial and MCU Runtime Stability Design

## Context

The host intermittently displays replacement characters in both the AT console and
the disabled pass-through page, then closes COM12 after an AT response timeout. The
MCU can also stop responding.

Baseline evidence collected on 2026-07-27:

- Host test suite: 179 passed.
- MCU Debug build: successful.
- COM12 stopped returning bytes after the reported failure.
- ST-Link halted at `Error_Handler`.
- The captured call stack was
  `USART1_IRQHandler -> HAL_UART_ErrorCallback ->
  App_RuntimeStartUart1Receive -> Error_Handler`.
- The UART error interrupted `HAL_UART_Transmit` while `App_AtReplySense` was
  sending a valid response.
- `g_app_diag.rx_error_count` was 1 and the UART1 ring still contained later AT
  commands.
- `STK_AT=176` words in the captured SENSE response, leaving about 704 bytes of
  atTask stack. This incident is therefore not the previous atTask stack overflow.

## Root causes

### MCU fatal recovery

For non-blocking noise, framing, or parity errors, STM32 HAL can consume the
received byte and invoke `HAL_UART_RxCpltCallback`, which immediately arms the next
one-byte receive. HAL then invokes `HAL_UART_ErrorCallback`. The application
unconditionally calls the strict startup helper again. Because reception is
already armed, `HAL_UART_Receive_IT` returns `HAL_BUSY`; the strict helper treats
that recoverable state as fatal and enters `Error_Handler`.

### Host protocol misclassification

The v2.2 UART tunnel is framed exclusively as `+UART2RX:<HEX>` and
`+UART3RX:<HEX>`. Nevertheless, every unknown CRLF-delimited line is still routed
as legacy raw pass-through data. A damaged AT response is therefore copied into
the third page even when no tunnel is enabled. Invalid UTF-8 is decoded through
Latin-1 and later decoded again with replacement characters, producing mojibake.

### Host timeout escalation

Any asynchronous command timeout currently closes the physical serial port.
Closing is not required when the port itself remains healthy. It also turns one
damaged response into a visible disconnect/reconnect cycle.

## Considered approaches

1. Fix only MCU UART recovery. This removes the observed fatal path but leaves the
   host vulnerable to other malformed responses and transient timeouts.
2. Fix both boundaries. Recover UART reception on the MCU; on the host, reject
   unframed data, render malformed bytes as hexadecimal diagnostics, and use a
   bounded quiet-period resynchronization without closing the port.
3. Replace the host FIFO with a global one-command scheduler. This provides the
   strongest response attribution but is a larger behavioral rewrite than the
   observed failures require.

Approach 2 is selected.

## MCU design

- Keep strict failure behavior for initial UART1 receive setup and normal
  receive-complete rearming.
- In `HAL_UART_ErrorCallback`, record the original HAL error flags before HAL
  clears them.
- Rearm only when `RxState == HAL_UART_STATE_READY`, which is the blocking ORE
  recovery case.
- Treat `HAL_UART_STATE_BUSY_RX` as already recovered. Do not call
  `Error_Handler`.
- Preserve the existing diagnostic counters and fault capture.

## Host design

- Invalid UTF-8 and unrecognized protocol lines are diagnostics, not pass-through
  payloads. Report their raw bytes as uppercase hexadecimal.
- Only valid `+UART2RX:` / `+UART3RX:` frames can feed the pass-through page.
- Ignore a valid UART event when the controller's confirmed tunnel mode is off.
- Render non-text tunnel payloads as hexadecimal instead of replacement
  characters.
- On an asynchronous timeout:
  - keep the transport open;
  - cancel all in-flight FIFO entries because attribution can no longer be
    guaranteed;
  - emit synthetic `TIMEOUT` responses so controller transitions roll back;
  - discard incoming bytes until a 200 ms quiet interval has elapsed;
  - reject new commands during that short resynchronization interval.
- Apply the same resynchronization boundary to synchronous handshake timeouts.

## Verification

- Host regression tests prove malformed bytes never reach pass-through UI,
  tunnel data is gated by confirmed mode, and asynchronous timeout keeps the
  transport open while discarding a late response.
- MCU builds with the bundled Cube CMake/GNU toolchain.
- Flash the resulting ELF using the connected ST-Link.
- Run repeated AT query traffic and inject wrong-baud/noise traffic.
- Verify the MCU remains responsive, `RX_ERR` can increase without a
  `+FAIL:H=` frame, and the host remains connected.
- Capture final task stack high-water marks with AT diagnostics and/or GDB.


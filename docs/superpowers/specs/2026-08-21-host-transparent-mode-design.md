# Host Exclusive Transparent Mode Design

## Goal

Update the PySide6 host to match the board-1 firmware's exclusive transparent
transfer contract at 9600 8N1 without changing the existing passthrough UI or
adding stall-current controls.

## Protocol and Session Model

The host keeps the existing `uart2`, `uart3`, `both`, and `off` UI modes. The
three active modes map to `AT+TRANS=1`, `AT+TRANS=2`, and `AT+TRANS=1&2`.
After the entry command returns `OK`, user payload is written as exact bytes;
the host no longer sends `AT+UART*=ON/OFF` or `AT+UARTTX=<HEX>`.

`SerialWorker` owns four communication states: AT, entering, transparent, and
exiting. Normal AT commands are accepted only in AT state, raw payload only in
transparent state, and no new user writes while a transition is active. Reverse
traffic remains line-framed as `+UART2RX:<HEX>` or `+UART3RX:<HEX>` and stays
outside the ordinary response FIFO.

Leaving transparent mode waits for 10 ms of host-side silence, writes exactly
`+++`, then sends nothing while waiting up to one second for `OK`. A successful
exit returns to AT mode and restarts polling. Switching targets exits the old
session before entering the new target. A standalone `+++` user payload is
rejected because the firmware reserves it as the guarded escape sequence.

## Failure Handling

Rejected or timed-out entry returns to AT state, leaves the UI mode off, and
resumes polling. Incomplete raw writes, exit write failures, exit timeout, or a
serial fault close the port because the host can no longer prove which mode the
MCU is in. Disconnect always clears transition timers, pending payload, and
session state.

## Verification

Automated tests cover all three mappings, exact binary writes, guarded exit,
entry and exit failures, rapid target changes, disconnection, reverse events,
and removal of every legacy command path. The fake firmware implements the new
session contract so controller and UI flows run end to end without hardware.

Release verification includes the complete pytest suite, Python compilation,
visual regression, PyInstaller packaging, and fake-mode launch smoke. Hardware
verification uses UART1 at 9600 8N1 and the currently connected UART3 adapter
for bidirectional raw transfer, embedded-plus replay, guarded exit, and return
to normal AT queries. UART2 and dual-target behavior are automation-only for
this delivery and must not be reported as hardware-verified.

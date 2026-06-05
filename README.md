# CS 5700 Project 4 - Reliable Transport

**Split:** Rohit = `4700send` (done), you = `4700recv` (your part).

---

## What's already done

### `4700send` (Rohit)

The sender is fully implemented. It:

- Reads from stdin until EOF, chunks data into 1200-byte packets
- Sends `data` packets with seq numbers `0, 1, 2, ...`
- Uses a sliding window (Go-Back-N), window starts at 4
- Retransmits on timeout; does fast retransmit after 3 duplicate ACKs
- Adjusts timeout based on RTT (starts at 1 second)
- After all data is acked, sends a `fin` packet
- Exits once `fin` is acked — prints `All done!` to stderr

### `packet.py` (shared)

Both programs use this file. It handles:

- JSON packet encoding/decoding
- CRC32 checksums (drop corrupted packets if `decode_packet` returns `None`)
- Helpers: `make_data_packet`, `make_ack_packet`, `make_fin_packet`, `extract_payload`

### `Makefile`

Just runs `chmod +x` on both scripts. Already set up.

### `4700recv` (stub only)

Right now it only binds to a port, prints `Bound to port <port>`, and logs incoming packets. **You need to implement the actual receiver logic here.**

---

## What you need to do (`4700recv`)

Build the receiver so it works with the sender's protocol below. Keep the starter-code style (class-based, log to stderr, print data to stdout).

### Required behavior (from the spec)

1. On startup, bind UDP and print exactly this as the **first** stderr line:
  ```
   Bound to port <port>
  ```
2. Receive packets from the sender, print the data to **stdout** in order with no errors
3. Send ACKs back over UDP
4. **Do not exit** on your own — the simulator kills the receiver after the sender exits

### Protocol to implement

All packets are JSON. Use `encode_packet` / `decode_packet` from `packet.py` for everything.


| type   | fields                 | meaning                                 |
| ------ | ---------------------- | --------------------------------------- |
| `data` | `seq`, `data` (base64) | one chunk of file data                  |
| `ack`  | `ack`                  | next seq number you expect (cumulative) |
| `fin`  | `seq`                  | end of transfer                         |


**ACK convention:** `ack` = the next sequence number you are waiting for (TCP-style).

Example: if you've received and printed packets 0, 1, 2 in order, send `ack: 3`.

### Step-by-step logic

```
next_expected = 0
buffer = {}   # seq -> bytes, for out-of-order packets

on each incoming UDP packet:
    pkt = decode_packet(raw)
    if pkt is None:
        ignore (corrupted)
        return

    remember sender's host/port from first valid packet
    ignore packets from other hosts

    if pkt["type"] == "data":
        seq = pkt["seq"]
        if seq < next_expected:
            pass  # duplicate, don't print again
        elif seq == next_expected:
            print extract_payload(pkt) to stdout
            next_expected += 1
            # drain buffer for anything now in order
            while next_expected in buffer:
                print buffer[next_expected] to stdout
                del buffer[next_expected]
                next_expected += 1
        else:  # seq > next_expected, out of order
            if seq not in buffer:
                buffer[seq] = extract_payload(pkt)

    elif pkt["type"] == "fin":
        if pkt["seq"] == next_expected:
            next_expected += 1
        # if fin arrives early, just buffer the situation via normal seq logic

    # always ack after a valid data or fin packet
    send encode_packet(make_ack_packet(next_expected)) back to sender
```

### Imports you'll need

```python
from packet import decode_packet, encode_packet, make_ack_packet, extract_payload
```

### Logging (stderr)

Match the starter code style — log received messages like:

```
Received message <raw bytes or decoded string>
```

The sender logs `Sending message '...'` and `Received message ...` the same way.

---

## How to test

1. Grab the official starter files from Khoury if we don't have them yet: `run`, `configs/`, `test`
2. Build:
  ```bash
   make
  ```
3. Run all tests:
  ```bash
   ./test
  ```
4. Debug one config:
  ```bash
   ./run configs/<some-config>
  ```

If you see `Success! Data was transmitted correctly.` you're good.

You can also test manually in two terminals:

```bash
# terminal 1
./4700recv

# terminal 2 (use the port from terminal 1)
echo "hello world" | ./4700send 127.0.0.1 <port>
```

---

## Files overview


| file        | owner  | status                 |
| ----------- | ------ | ---------------------- |
| `4700send`  | Rohit  | done                   |
| `4700recv`  | Aditya | **you implement this** |
| `packet.py` | shared | done                   |
| `Makefile`  | shared | done                   |



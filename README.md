# CS 5700 Project 4 - Reliable Transport

A UDP-based reliable transport for sending a file from stdin to a remote receiver. `4700send` reads data, breaks it into packets, and sends them over UDP. `4700recv` receives packets, prints the data to stdout in order, and sends ACKs back. The simulator in `run` drops, delays, reorders, duplicates, and corrupts packets to test that the transfer still works.

## Files

- `4700send` - sender. Reads stdin, sends data packets, handles retransmits.
- `4700recv` - receiver. Binds a UDP port, prints data to stdout, sends ACKs.
- `packet.py` - shared packet encoding, checksums, and helpers.
- `Makefile` - runs `chmod +x` on both programs.
- `run` - simulator.
- `test` - runs all config files in `configs/`.
- `configs/` - network test configs from the starter repo.
- `README.md` - this file.

## Build and run

```bash
make
./test
```

To run one config:

```bash
./run configs/1-1-basic.conf
```

Manual test in two terminals:

```bash
# terminal 1
./4700recv

# terminal 2 - use the port printed by the receiver
echo "hello world" | ./4700send 127.0.0.1 <port>
```

`4700send` takes `<host> <port>` and reads from stdin until EOF. It exits once the receiver has acked everything including the FIN packet. `4700recv` takes no arguments, prints `Bound to port <port>` as its first stderr line, and never exits on its own (the simulator kills it after the sender finishes).

Debug output goes to stderr. Only the received file data goes to stdout on the receiver.

## Approach

### Packet format

All packets are JSON with a CRC32 checksum field. `packet.py` handles encode/decode and drops anything that fails the checksum.


| type   | fields                 | meaning                               |
| ------ | ---------------------- | ------------------------------------- |
| `data` | `seq`, `data` (base64) | one chunk of file data                |
| `ack`  | `ack`                  | next seq number expected (cumulative) |
| `fin`  | `seq`                  | end of transfer                       |


Raw payload per data packet is capped at 1070 bytes so the full encoded UDP datagram stays under the 1500-byte limit.

### Sender (`4700send`)

The sender uses a sliding window (Go-Back-N). Sequence numbers start at 0. It reads stdin in chunks, sends data packets while the window allows, and waits for cumulative ACKs.

- Window starts at 3 and grows by 1 on each new ACK, up to 20.
- On timeout, the window halves and up to 4 unacked packets are retransmitted.
- Two duplicate ACKs for the same base trigger a fast retransmit of the oldest unacked packet.
- RTO starts at 0.5s. Before the first RTT sample, timeouts wait at least 1.0s so early packets are not retransmitted too soon on high-delay links. After that, RTO is based on measured RTT (`max(2 * srtt, srtt + 4 * rttvar)`).
- Corrupted ACKs are ignored (treated like a lost packet).
- After stdin EOF and all data is acked, the sender sends a `fin` packet and exits once that is acked.

The main loop uses `select` on the socket, stdin, and a retransmit timer. `fill_window()` sends as many new packets as the window allows instead of waiting one select cycle per packet.

### Receiver (`4700recv`)

The receiver tracks `next_expected` (starts at 0) and a buffer dict for out-of-order packets.

- On an in-order `data` packet, it writes the payload to stdout and bumps `next_expected`.
- Out-of-order packets go into the buffer. `drain()` prints anything that is now contiguous.
- Duplicates (`seq < next_expected`) are ignored.
- Corrupted packets are dropped with no ACK.
- On a valid `fin` with the right seq, it advances past the fin and keeps running.
- Every valid `data` or `fin` packet gets an ACK with the current `next_expected`.

Data is written with `sys.stdout.buffer.write` so binary content is not mangled.

## Challenges

**Packet size.** First version used 1200-byte payloads. Base64 plus JSON plus the checksum pushed packets over 1500 bytes and the simulator dropped them. Lowered `MAX_PAYLOAD_SIZE` to 1070 after checking encoded size.

**Retransmit overhead.** Retransmitting the entire window on every timeout passed correctness tests but blew past the byte overhead limits on several configs. Capped timeout retransmits to 4 packets and only retransmit the base packet on fast retransmit.

**Jitter and lifetime limits.** On `3-2-more-jitter.conf` the sender was running out of time because INITIAL_RTO of 0.5s fired before the first ACK on a 0.5s-delay link. Added `FIRST_ACK_RTO` so the first timeout waits at least 1.0s, then switches to the measured RTT.

**Out-of-order delivery.** Level 3 configs deliver packets out of order. The receiver buffers anything ahead of `next_expected` and drains when the gap fills in. The sender keeps multiple packets in flight with the sliding window.

**Corrupted packets.** Level 5 configs mangle packets. Both sides use `decode_packet()` from `packet.py` and treat a bad checksum as a lost packet.

## Testing

Ran `./test` locally. All 18 configs pass:

- 1-1, 1-2: basic transfer
- 2-1: duplicates
- 3-1, 3-2: jitter
- 4-1, 4-2: drops
- 5-1, 5-2: corruption (mangle)
- 6-1, 6-2, 6-3: latency
- 7-1, 7-2, 7-3: bandwidth
- 8-1, 8-2, 8-3: combined stress tests

For a failing config, `./run configs/<name>` prints full sender and receiver logs plus whether data matched and byte overhead stats. Also tested manually with `echo "hello world" | ./4700send 127.0.0.1 <port>` against a running `./4700recv`.
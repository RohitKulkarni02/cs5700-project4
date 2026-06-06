# CS 5700 Project 4 - Reliable Transport

A UDP-based reliable transport protocol that transfers data from stdin to a remote receiver despite loss, corruption, duplication, delay, and reordering. `4700send` reads data, breaks it into packets, and sends them over UDP. `4700recv` receives packets, prints the data to stdout in order, and sends ACKs back. The simulator in `run` drops, delays, reorders, duplicates, and corrupts packets to test that the transfer still works.

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

Packets use a compact binary header followed by the raw payload. `packet.py` handles encode/decode and drops anything that fails the checksum.

| field | size | meaning |
| ----- | ---- | ------- |
| type | 1 byte | 0 = data, 1 = ack, 2 = fin |
| seq | 4 bytes | sequence number (for ack, the next seq expected) |
| checksum | 4 bytes | CRC32 over type, seq, and payload |
| payload | variable | raw file data (data packets only) |

The header is 9 bytes, so the raw payload is capped at 1472 bytes to keep the whole datagram at or under the 1500-byte limit. Keeping the payload raw (instead of base64 text in JSON) avoids about a third of the per-byte overhead and lets each packet carry more data.

### Sender (`4700send`)

The sender uses a sliding window (Go-Back-N). Sequence numbers start at 0. It reads stdin in chunks, sends data packets while the window allows, and waits for cumulative ACKs.

- Window starts at 3 and grows by 1 on each new ACK, up to 20.
- On timeout, the window halves and up to 4 unacked packets are retransmitted.
- Three duplicate ACKs for the same base trigger a fast retransmit of the oldest unacked packet. The threshold is set at three because the test networks duplicate ACKs, and a lower value caused unnecessary resends.
- RTO starts at 0.5s. Before the first RTT sample, timeouts wait at least 1.0s so early packets are not retransmitted too soon on high-delay links. After that, RTO is based on measured RTT (`max(2 * srtt, srtt + 4 * rttvar)`).
- Corrupted ACKs are ignored (treated like a lost packet).
- After stdin EOF and all data is acked, the sender sends a `fin` packet and exits once that is acked.

The main loop uses `select` on the socket and stdin (when the window has room), with a timeout for retransmits. `fill_window()` sends as many new packets as the window allows instead of waiting one select cycle per packet.

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

**Encoding overhead.** An early version put base64-encoded data inside JSON. Base64 adds about a third to every byte and JSON adds more, which both pushed packets near the 1500-byte limit and inflated the total bytes sent. Switching to a binary header with a raw payload cut the per-byte overhead to almost nothing and let each packet carry 1472 bytes instead of 1070.

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

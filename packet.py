#!/usr/bin/env python3

import struct
import zlib


MAX_PACKET_SIZE = 1500
# 9-byte header (type + seq + checksum) leaves room for the payload while
# keeping the whole datagram at or under the 1500-byte limit.
MAX_PAYLOAD_SIZE = 1472

TYPE_CODE = {"data": 0, "ack": 1, "fin": 2}
CODE_TYPE = {0: "data", 1: "ack", 2: "fin"}

HEADER = struct.Struct("!BII")
HEAD_NO_CRC = struct.Struct("!BI")


def encode_packet(packet):
    """
    Turn a packet dict into bytes: type, seq, CRC32, then the raw payload.
    The checksum covers the type, seq, and payload.
    """

    kind = packet["type"]
    code = TYPE_CODE[kind]

    if kind == "ack":
        seq = packet["ack"]
        payload = b""
    else:
        seq = packet["seq"]
        payload = packet.get("payload", b"")

    head = HEAD_NO_CRC.pack(code, seq)
    checksum = zlib.crc32(head + payload) & 0xffffffff

    return HEADER.pack(code, seq, checksum) + payload


def decode_packet(raw_data):
    """
    Parse bytes back into a packet dict, returning None if the packet is
    too short, has an unknown type, or fails the checksum.
    """

    if len(raw_data) < HEADER.size:
        return None

    try:
        code, seq, checksum = HEADER.unpack(raw_data[:HEADER.size])
    except struct.error:
        return None

    payload = raw_data[HEADER.size:]
    expected = zlib.crc32(raw_data[:HEAD_NO_CRC.size] + payload) & 0xffffffff
    if checksum != expected:
        return None

    kind = CODE_TYPE.get(code)
    if kind is None:
        return None

    if kind == "ack":
        return {"type": "ack", "ack": seq}
    if kind == "fin":
        return {"type": "fin", "seq": seq}
    return {"type": "data", "seq": seq, "payload": payload}


def make_data_packet(seq, payload):
    """Create a data packet. payload should be bytes."""

    return {"type": "data", "seq": seq, "payload": payload}


def make_ack_packet(next_expected):
    """Create an ACK packet. ack is the next seq number the receiver expects."""

    return {"type": "ack", "ack": next_expected}


def make_fin_packet(seq):
    """Create an end-of-transfer packet."""

    return {"type": "fin", "seq": seq}


def extract_payload(packet):
    """Return the raw payload bytes from a data packet."""

    return packet["payload"]

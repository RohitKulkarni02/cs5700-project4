#!/usr/bin/env python3

import json
import zlib
import base64


MAX_PACKET_SIZE = 1500
MAX_PAYLOAD_SIZE = 1200


def compute_checksum(packet):
    """
    Compute CRC32 checksum over packet contents
    excluding the checksum field itself.
    """

    temp = dict(packet)

    if "checksum" in temp:
        del temp["checksum"]

    payload = json.dumps(
        temp,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    return zlib.crc32(payload) & 0xffffffff


def encode_packet(packet):
    """
    Add checksum and convert packet to bytes.
    """

    pkt = dict(packet)
    pkt["checksum"] = compute_checksum(pkt)

    return json.dumps(pkt).encode("utf-8")


def decode_packet(raw_data):
    """
    Decode packet and verify checksum.

    Returns:
        packet dictionary if valid
        None if corrupted
    """

    try:
        packet = json.loads(raw_data.decode("utf-8"))

        if "checksum" not in packet:
            return None

        received_checksum = packet["checksum"]
        expected_checksum = compute_checksum(packet)

        if received_checksum != expected_checksum:
            return None

        return packet

    except Exception:
        return None


def make_data_packet(seq, payload):
    """
    Create a data packet.

    payload should be bytes.
    """

    encoded_payload = base64.b64encode(payload).decode("utf-8")

    return {
        "type": "data",
        "seq": seq,
        "data": encoded_payload
    }


def make_ack_packet(next_expected):
    """
    Create an ACK packet. ack is the next seq number the receiver expects.
    """

    return {
        "type": "ack",
        "ack": next_expected
    }


def make_fin_packet(seq):
    """
    Create end-of-transfer packet.
    """

    return {
        "type": "fin",
        "seq": seq
    }


def extract_payload(packet):
    """
    Convert packet payload back to bytes.
    """

    return base64.b64decode(packet["data"])
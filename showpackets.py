#!/bin/env python3
import time
import socket
import random
import argparse

from pynanocoin import *
from msg_handshake import *
from peercrawler import *
from confirm_req import *
from msg_publish import *
from frontier_request import *
from bulk_pull_account import *
from telemetry_req import *


def parse_args():
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-b', '--beta', action='store_true', default=False,
                       help='use beta network')
    group.add_argument('-t', '--test', action='store_true', default=False,
                       help='use test network')

    parser.add_argument('--peer',
                        help='peer to contact')

    parser.add_argument('-k', '--keepalive', action='store_true', default=False,
                        help='indicates the script to show keepalives')
    parser.add_argument('-c', '--confirm_req', action='store_true', default=False,
                        help='indicated the script to show confirm requests')
    parser.add_argument('-C', '--confirm_ack', action='store_true', default=False,
                        help='indicates the script to show confirm acks')
    parser.add_argument('-p', '--publish', action='store_true', default=False,
                        help='indicates to show msg_publish packets')
    parser.add_argument('-P', '--bulk_pull', action='store_true', default=False,
                        help='indicates to show bulk_pull packets')
    parser.add_argument('-B', '--bulk_push', action='store_true', default=False,
                        help='indicates to show bulk_push packets')
    parser.add_argument('-f', '--frontier_req', action='store_true', default=False,
                        help='indicates to show frontier_req packets')
    parser.add_argument('-H', '--handshake', action='store_true', default=False,
                        help='indicates to show node_id_handshake packets')
    parser.add_argument('-a', '--bulk_pull_acc', action='store_true', default=False,
                        help='indicates to show bulk_pull_account packets')
    parser.add_argument('--tr', dest='telemetry_req', action='store_true', default=False,
                        help='indicates to show telemetry_req packets')
    parser.add_argument('--ta', dest='telemetry_ack', action='store_true', default=False,
                        help='indicates to show telemetry_ack packets')
    parser.add_argument('--all', action='store_true', default=False,
                        help='indicates to show all packets')

    return parser.parse_args()


def confirm_req_func(hdr, payload):
    if hdr.block_type() == block_type_enum.not_a_block:
        req = confirm_req_hash.parse(hdr, payload)
    else:
        req = confirm_req_block.parse(hdr, payload)
    return req


def node_handshake_id(hdr, payload):
    if hdr.is_query() and hdr.is_response():
        handshake = handshake_response_query.parse_query_response(hdr, payload)
    elif hdr.is_query():
        handshake = handshake_query.parse_query(hdr, payload)
    elif hdr.is_response():
        handshake = handshake_response.parse_response(hdr, payload)
    return handshake


functions = {
    message_type_enum.keepalive: message_keepalive.parse_payload,
    message_type_enum.publish: msg_publish.parse,
    message_type_enum.confirm_req: confirm_req_func,
    message_type_enum.confirm_ack: confirm_ack.parse,
    message_type_enum.bulk_pull: message_bulk_pull.parse,
    message_type_enum.bulk_push: bulk_push.parse,
    message_type_enum.frontier_req: frontier_request.parse,
    message_type_enum.node_id_handshake: node_handshake_id,
    message_type_enum.bulk_pull_account: bulk_pull_account.parse,
    message_type_enum.telemetry_req: lambda hdr, payload: hdr,
    message_type_enum.telemetry_ack: telemetry_ack.parse,
    message_type_enum.not_a_block: lambda hdr, payload: hdr
}


def set_functions(args):
    if args.all:
        return
    if not args.keepalive:
        functions.pop(message_type_enum.keepalive)
    if not args.publish:
        functions.pop(message_type_enum.publish)
    if not args.confirm_req:
        functions.pop(message_type_enum.confirm_req)
    if not args.confirm_ack:
        functions.pop(message_type_enum.confirm_ack)
    if not args.bulk_pull:
        functions.pop(message_type_enum.bulk_pull)
    if not args.bulk_push:
        functions.pop(message_type_enum.bulk_push)
    if not args.frontier_req:
        functions.pop(message_type_enum.frontier_req)
    if not args.handshake:
        functions.pop(message_type_enum.node_id_handshake)
    if not args.bulk_pull_acc:
        functions.pop(message_type_enum.bulk_pull_account)
    if not args.telemetry_req:
        functions.pop(message_type_enum.telemetry_req)
    if not args.telemetry_ack:
        functions.pop(message_type_enum.telemetry_ack)


def main():
    args = parse_args()
    set_functions(args)

    ctx = livectx
    if args.beta: ctx = betactx
    elif args.test: ctx = testctx

    if args.peer:
        peeraddr, peerport = parse_endpoint(args.peer, default_port=ctx['peerport'])
    else:
        peer = get_random_peer(ctx, lambda p: p.score >= 1000)
        peeraddr, peerport = str(peer.ip), peer.port

    print('Conneting to [%s]:%s' % (peeraddr, peerport))
    with get_connected_socket_endpoint(peeraddr, peerport) as s:
        perform_handshake_exchange(ctx, s)

        # send a keepalive, this is not necessary, just doing it as an example
        hdr = message_header(ctx['net_id'], [18, 18, 18], message_type(message_type_enum.keepalive), 0)
        keepalive = message_keepalive(hdr)
        req = keepalive.serialise()
        s.send(req)

        # now we are waiting for keepalives, so set a long timeout (60 minutes)
        s.settimeout(60 * 60)

        while True:
            hdr, payload = get_next_hdr_payload(s)
            # TODO: this if statement should not be necessary, we just need a mapping
            # from message type to handler function and this big if can disapper
            if hdr.msg_type.type in functions:
                print(functions[hdr.msg_type.type](hdr, payload))


if __name__ == "__main__":
    main()

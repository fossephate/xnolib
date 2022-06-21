#!/bin/env python3

from __future__ import annotations

import time
from datetime import datetime, timedelta
import random
import threading
import argparse
from subprocess import run

from flask import Flask, Response, render_template, request
from flask_caching import Cache

import jsonencoder
import peercrawler
from typing import Callable
from pynanocoin import Peer
from acctools import to_account_addr
from representative_mapping import representative_mapping
from _logger import setup_logger, get_logger, get_logging_level_from_int
from pynanocoin import livectx, betactx, testctx


app = Flask(__name__, static_url_path='/peercrawler')
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

logger = get_logger()

peerman: peercrawler.peer_manager = None

representatives = representative_mapping()
representatives.load_from_file("representative-mappings.json")
threading.Thread(target=representatives.load_from_url_loop, args=("https://nano.community/data/representative-mappings.json", 3600), daemon=True).start()


def bg_thread_func(ctx: dict, listen: bool, listen_port: int, delay: int, verbosity: int):
    global peerman

    peerman = peercrawler.peer_manager(ctx, listen=listen, listening_port=listen_port, verbosity=verbosity)
    peerman.crawl(forever=True, delay=delay)  # look for peers forever


@app.route("/peercrawler")
@cache.cached(timeout=5)
def main_website():
    return render_template('index.html')


@app.route("/peercrawler/formatted", methods=['GET'])
def data():
    global app, peerman, representatives
    
    peers_copy = list(peerman.get_peers_as_list())

    peer_list = []
    for peer in peers_copy:
        telemetry = peer.telemetry

        row = {}

        row["ip_port"] = str(peer.ip) + ":" + str(peer.port)
        row["is_voting"] = peer.is_voting

        if peer.score != None and peer.score != 0 and peer.score != -1:
            row["score"] = peer.score

        # TODO:
        if False:
            row["is_PR"] = True
        else:
            row["is_PR"] = False

        if telemetry != None:
            node_id = to_account_addr(telemetry.node_id, "node_")
            representative_info = representatives.find(node_id, str(peer.ip))
            aliases = [r.get("alias", " ") for r in representative_info]
            accounts = [r.get("account", " ") for r in representative_info]
            weights = [r.get("weight", " ") for r in representative_info]

            # " // ".join(filter(lambda n: isinstance(n, str), aliases)),  # filter out None values

            row["node_id"] = node_id
            row["aliases"] = list(filter(lambda n: isinstance(n, str), aliases))
            row["accounts"] = list(filter(lambda n: isinstance(n, str), accounts))
            row["weights"] = list(filter(lambda n: isinstance(n, str), weights))


            row["account_count"] = telemetry.account_count
            row["bandwidth_cap"] = telemetry.bandwidth_cap
            row["peer_count"] = telemetry.peer_count
            row["protocol_ver"] = telemetry.protocol_ver

            # row["block_count"] = telemetry.block_count
            # row["cemented_count"] = telemetry.cemented_count
            # row["unchecked_count"] = telemetry.unchecked_count
            # combined:
            # row["block_counts"] = f"{telemetry.block_count}:{telemetry.cemented_count}:{telemetry.unchecked_count}"
            row["block_counts"] = {
                "block_count": telemetry.block_count,
                "cemented_count": telemetry.cemented_count,
                "unchecked_count": telemetry.unchecked_count
            }


            #                   str(timedelta(seconds=telemetry.uptime)),
            #                   telemetry.uptime,
            #                   f"{telemetry.major_ver} {telemetry.minor_ver} {telemetry.patch_ver} {telemetry.pre_release_ver} {telemetry.maker_ver}",
            #                   datetime.utcfromtimestamp(telemetry.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            #                   telemetry.timestamp,
            #                   telemetry.sig_verified,
            row["timestamp"] = telemetry.timestamp
            row["uptime"] = telemetry.uptime
            row["sig_verified"] = telemetry.sig_verified
            row["sw_version"] = f"{telemetry.major_ver} {telemetry.minor_ver} {telemetry.patch_ver} {telemetry.pre_release_ver} {telemetry.maker_ver}"
            row["timestamp2"] = datetime.utcfromtimestamp(telemetry.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')



            # peer_list.append([peer.ip,
            #                   peer.port,
            #                   " // ".join(filter(lambda n: isinstance(n, str), aliases)),  # filter out None values
            #                   filter(lambda n: isinstance(n, str), accounts),
            #                   peer.is_voting,
            #                   telemetry.sig_verified,
            #                   node_id,
            #                   " // ".join(filter(lambda n: n is not None, weights)),
            #                   telemetry.block_count,
            #                   telemetry.cemented_count,
            #                   telemetry.unchecked_count,
            #                   telemetry.account_count,
            #                   telemetry.bandwidth_cap,
            #                   telemetry.peer_count,
            #                   telemetry.protocol_ver,
            #                   str(timedelta(seconds=telemetry.uptime)),
            #                   telemetry.uptime,
            #                   f"{telemetry.major_ver} {telemetry.minor_ver} {telemetry.patch_ver} {telemetry.pre_release_ver} {telemetry.maker_ver}",
            #                   datetime.utcfromtimestamp(telemetry.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            #                   telemetry.timestamp,
            #                   peer.score])
        peer_list.append(row)
    js = jsonencoder.to_json(peer_list)
    return Response(js, status=200, mimetype="application/json")


@app.route("/peercrawler/json", methods=['GET'])
def json():
    peers = peerman.get_peers_as_list()
    js = jsonencoder.to_json(list(peers))

    return Response(js, status=200, mimetype="application/json")


@app.route("/peercrawler/logs")
def logs():
    log_file_name = "peercrawler.log"

    try:
        with open(log_file_name + ".1", mode="r", encoding="UTF-8") as f:
            log_1 = f.read()
    except FileNotFoundError:
        log_1 = ""

    try:
        with open(log_file_name, mode="r") as f:
            log_2 = f.read()
    except FileNotFoundError:
        log_2 = ""

    return Response(log_1 + log_2, status=200, mimetype="text/plain")


@app.route("/peercrawler/graph")
def graph():
    if not app.config["args"].enable_graph:
        return Response(status=404)

    with open("peers.svg", "rb") as file:
        svg = file.read()

    return Response(svg, status=200, mimetype="image/svg+xml")


@app.route("/peercrawler/graph/raw")
@cache.cached(timeout=10)
def graph_raw():
    if not app.config["args"].enable_graph:
        return Response(status=404)

    dot = peerman.get_dot_string(make_filter_from_query_parameters())
    return Response(dot, status=200, mimetype="text/plain")


@app.route("/peercrawler/graph/uncached")
def graph_uncached():
    if not app.config["args"].enable_graph or not app.config["args"].graph_uncached:
        return Response(status=404)

    svg = render_graph_svg(make_filter_from_query_parameters())
    return Response(svg, status=200, mimetype="image/svg+xml")


def make_filter_from_query_parameters() -> Callable[[Peer, Peer], bool]:
    minimum_score = request.args.get("score", default=0, type=int)
    only_voting = request.args.get("only-voting", default=True, type=lambda q: q.lower() == "true")

    def peer_filter(p1: Peer, p2: Peer) -> bool:
        if only_voting is True and (not p1.is_voting or not p2.is_voting):
            return False
        if p1.score < minimum_score or p2.score < minimum_score:
            return False

        return True

    return peer_filter


def render_graph_svg(filter_function: Callable[[Peer, Peer], bool] = None) -> bytes:
    dot = peerman.get_dot_string(filter_function)
    svg = run(["circo", "-Tsvg"], input=bytes(dot, encoding="utf8"), capture_output=True).stdout
    return svg


def render_graph_thread(interval_seconds: int):
    time.sleep(10)

    while True:
        svg = render_graph_svg()
        with open("peers.svg", "wb") as file:
            file.write(svg)

        time.sleep(interval_seconds)


def parse_args():
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-b", "--beta", action="store_true", default=False,
                       help="use beta network")
    group.add_argument("-t", "--test", action="store_true", default=False,
                       help="use test network")

    parser.add_argument("-v", "--verbosity", type=int, default=0,
                        help="verbosity level")
    parser.add_argument("-d", "--delay", type=int, default=300,
                        help="delay between crawls in seconds")
    parser.add_argument("-l", "--nolisten", action="store_true", default=False,
                        help="disable incoming connection listener for other peers in the network")
    parser.add_argument("-p", "--port", type=int, default=7777,
                        help="port to listen on for incoming requests from other peers in the network")
    parser.add_argument("--http-port", type=int, default=5001,
                        help="port to listen on for incoming HTTP requests")
    parser.add_argument("-g", "--enable-graph", action="store_true", default=False,
                        help="enables the graph endpoints; the graphviz binaries need to be in the PATH for the script to access them")
    parser.add_argument("--graph-interval", type=int, default=3600,
                        help="how many seconds to wait between rendering the graph; this has no effect if the graph generation feature is not enabled")
    parser.add_argument("--graph-uncached", action="store_true", default=False,
                        help="enables the graph endpoint which serves rendered graphs on demand; this has no effect if the graph generation feature is not enabled")

    return parser.parse_args()


def main():
    args = parse_args()
    app.config["args"] = args

    if args.beta:
        ctx = betactx
    elif args.test:
        ctx = testctx
    else:
        ctx = livectx

    setup_logger(logger, get_logging_level_from_int(args.verbosity))

    # start the peer crawler in the background
    threading.Thread(target=bg_thread_func, args=(ctx, not args.nolisten, args.port, args.delay, args.verbosity), daemon=True).start()

    if args.enable_graph:
        threading.Thread(target=render_graph_thread, args=(args.graph_interval,), daemon=True).start()

    # start flash server in the foreground or debug=True cannot be used otherwise
    # flask expects to be in the foreground
    app.run(host='0.0.0.0', port=args.http_port, debug=False)


if __name__ == "__main__":
    main()

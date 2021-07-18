#!/bin/env python3
import socket
import time
import sys
import tempfile

import peercrawler
from nanolib import *


def pull_blocks(blockman, peer, hsh):
    print('pull blocks for account %s' % hsh)
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        s.settimeout(1)
        s.connect((str(peer.ip), peer.port))

        # send a block pull request
        hdr = message_header(network_id(67), [18, 18, 18], message_type(6), 0)
        bulk_pull = message_bulk_pull(hdr, hsh)
        s.send(bulk_pull.serialise())

        # pull blocks from peer
        while True:
            block = read_block_from_socket(s)
            if block is None:
                break
            block.ancillary['peers'].add('[%s]:%s' % (peer.ip, peer.port))
            print(block)
            blockman.process(block)

        #a, b = blockman.accounts[0].check_forks()
        #if a is not None or b is not None:
        #    print("Found forks in peer: %s" % str(peer))
        #    print("The following blocks have the same previous link:")
        #    print(a)
        #    print(b)


peercrawler_thread = peercrawler.spawn_peer_crawler_thread(ctx=livectx, forever=True, delay=30)
peerman = peercrawler_thread.peerman
time.sleep(1)

fork1 = '7D6FE3ABD8E2F7598911E13DC9C5CD2E71210C1FBD90D503C7A2041FBF58EEFD'
fork2 = 'CC83DA473B2B1BA277F64359197D4A36866CC84A7D43B1F65457324497C75F75'

acc_ids = [
    livectx["genesis_pub"],
    '42DD308BA91AA225B9DD0EF15A68A8DD49E2940C6277A4BFAC363E1C8BF14279',
#    '3309D2BDB2DCE1C5744F357E39DC8AC85980F00499F8F43B0A1287D0658C7173',
    fork1,
    fork2,
]

os.makedirs('forkdetector.data', exist_ok=True)
workdir = tempfile.mkdtemp(dir='forkdetector.data')
print(workdir)

# initialise a git project in the temporary work directory
gitrepo = git.Repo.init(workdir)

blockman = block_manager(workdir, gitrepo)
stop = False
while len(blockman.accounts) < 2 or not blockman.accounts[1].isforked:
    peers = peerman.get_peers_copy()
    print()
    print('Starting a round of pulling blocks with %s peers' % len(peers))
    pulls = 0
    for peer in peers:
        try:
            pull_blocks(blockman, peer, fork2)
            pulls += 1
#            if pulls >= 1:
#                stop = True
#                break
        except socket.error as error:
            peer.score = 0
            print('socket error %s' % error)

    #print(blockman.accounts[0].str_blocks())
    #for acc in blockman.accounts:
    #    print(acc)
    #print(blockman)
    #time.sleep(3)

#print(blockman.unprocessed_blocks[0])
for acc in blockman.accounts:
    print(acc)
print(blockman)
print(workdir)

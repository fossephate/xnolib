
from hashlib import blake2b
import binascii
import ipaddress
import socket
import base64
import dns.resolver
import random

import ed25519_blake2


class ParseErrorBadMagicNumber(Exception): pass


class ParseErrorBadNetworkId(Exception): pass


class ParseErrorBadMessageType(Exception): pass


class ParseErrorBadIPv6(Exception): pass


class ParseErrorBadMessageBody(Exception): pass


class ParseErrorBadBlockSend(Exception): pass


class ParseErrorBadBlockReceive(Exception): pass


class ParseErrorBadBlockOpen(Exception): pass


class ParseErrorBadBlockChange(Exception): pass


class ParseErrorBadBlockChange(Exception): pass


class ParseErrorBadBlockState(Exception): pass


class ParseErrorBadBulkPullResponse(Exception): pass


class BadBlockHash(Exception): pass


class SocketClosedByPeer(Exception): pass


class InvalidBlockHash(Exception): pass


class ProcessingErrorAccountAlreadyOpen(Exception): pass


def account_id_to_name(acc_id_bin):
    assert (len(acc_id_bin) == 32)

    genesis_live = binascii.unhexlify('E89208DD038FBB269987689621D52292AE9C35941A7484756ECCED92A65093BA')
    genesis_beta = binascii.unhexlify('259A43ABDB779E97452E188BA3EB951B41C961D3318CA6B925380F4D99F0577A')
    burn = b'\x00' * 32

    named_accounts = {
        genesis_live : 'genesis live',
        genesis_beta : 'genesis beta',
        burn : 'burn',
    }

    return named_accounts.get(acc_id_bin, '')


def get_all_dns_addresses(url):
    result = dns.resolver.resolve(url, 'A')
    return [x.to_text() for x in result]


# this function expects account to be a 32 byte bytearray
def get_account_id(account, prefix='nano_'):
    assert (len(account) == 32)

    RFC_3548 = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    ENCODING = b"13456789abcdefghijkmnopqrstuwxyz"

    h = blake2b(digest_size=5)
    h.update(account)
    checksum = h.digest()

    # prefix account to make it even length for base32, add checksum in reverse byte order
    account2 = b'\x00\x00\x00' + account + checksum[::-1]

    # use the optimized base32 lib to speed this up
    encode_account = base64.b32encode(account2)

    # simply translate the result from RFC3548 to Nano's encoding, snip off the leading useless bytes
    encode_account = encode_account.translate(bytes.maketrans(RFC_3548, ENCODING))[4:]

    label = account_id_to_name(account)
    if label != '':
        label = ' (' + label + ')'

    # add prefix, label and return
    return prefix + encode_account.decode() + label


class block_type_enum:
    invalid = 0
    not_a_block = 1
    send = 2
    receive = 3
    open = 4
    change = 5
    state = 6


class message_type_enum:
    invalid = 0x0
    not_a_type = 0x1
    keepalive = 0x2
    publish = 0x3
    confirm_req = 0x4
    confirm_ack = 0x5
    bulk_pull = 0x6
    bulk_push = 0x7
    frontier_req = 0x8
    # deleted 0x9
    node_id_handshake = 0x0a
    bulk_pull_account = 0x0b
    telemetry_req = 0x0c
    telemetry_ack = 0x0d


class network_id:
    def __init__(self, rawbyte):
        self.parse_header(int(rawbyte))

    def parse_header(self, rawbyte):
        # if not (rawbyte in [ord('A'), ord('B'), ord('C')]):
        #     raise ParseErrorBadNetworkId()
        self.id = rawbyte

    def __str__(self):
        return chr(self.id)


class message_type:
    def __init__(self, data):
        self.parse_type(data)

    def parse_type(self, data):
        # if not (data in range(2, 13)):
        #      raise ParseErrorBadMessageType()
        self.type = data

    def __str__(self):
        return str(self.type)


class message_header:

    def __init__(self, net_id, versions, msg_type, ext):
        self.ext = ext
        self.net_id = net_id
        self.ver_max = versions[0]
        self.ver_using = versions[1]
        self.ver_min = versions[2]
        self.msg_type = msg_type

    def serialise_header(self):
        header = b""
        header += ord('R').to_bytes(1, "big")
        header += ord(str(self.net_id)).to_bytes(1, "big")
        header += self.ver_max.to_bytes(1, "big")
        header += self.ver_using.to_bytes(1, "big")
        header += self.ver_min.to_bytes(1, "big")
        header += self.msg_type.type.to_bytes(1, "big")
        header += (00).to_bytes(1, "big")
        header += (00).to_bytes(1, "big")
        return header

    # this need to become a class method
    @classmethod
    def parse_header(cls, data):
        # if data[0] != ord('R'):
        #     raise ParseErrorBadMagicNumber()
        ext = []
        net_id = network_id(data[1])
        versions = []
        versions.append(data[2])
        versions.append(data[3])
        versions.append(data[4])
        msg_type = message_type(data[5])
        ext.append(data[6])
        ext.append(data[7])
        return message_header(net_id, versions, msg_type, ext)

    def __eq__(self, other):
        if str(self) == str(other):
            return True

    def __str__(self):
        str = "NetID:%s, " % self.net_id
        str += "VerMax:%s, " % self.ver_max
        str += "VerUsing:%s, " % self.ver_using
        str += "VerMin:%s, " % self.ver_min
        str += "MsgType:%s, " % self.msg_type
        str += "Extensions:%s, %s" % (self.ext[0], self.ext[1])
        return str


class ipv6addresss:
    def __init__(self, ip):
        self.ip = ip

    @classmethod
    def parse_address(cls, data):
        if len(data) < 16:
            raise ParseErrorBadIPv6
        address_int = int.from_bytes(data[0:16], "big")
        return ipv6addresss(ipaddress.IPv6Address(address_int))

    def __str__(self):
        return str(self.ip)


# A class representing a peer, stores its address, port and provides the means to convert
# it into a readable string format
class peer_address:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def serialise(self):
        data = b""
        data += self.ip.ip.packed
        data += self.port.to_bytes(2, "little")
        return data

    def __str__(self):
        string = "["
        string += str(self.ip) + "]:"
        string += str(self.port)
        return string


# Creates, stores and manages all of the peer_address objects (from the raw data)
class peers():
    def __init__(self, peers):
        self.peers = peers

    @classmethod
    def parse_peers(cls, rawdata):
        if len(rawdata) % 18 != 0:
            raise ParseErrorBadMessageBody()
        no_of_peers = int(len(rawdata) / 18)
        start_index = 0
        end_index = 18
        peers_list = []
        for i in range(0, no_of_peers):
            ip = ipv6addresss.parse_address(rawdata[start_index:end_index - 2])
            port = int.from_bytes(rawdata[end_index - 2:end_index], "little")
            p = peer_address(ip, port)
            peers_list.append(p)
            start_index = end_index
            end_index += 18
        return peers(peers_list)

    def serialise(self):
        data = b""
        for i in range(0, len(self.peers)):
            data += self.peers[i].serialise()
        return data

    def __eq__(self, other):
        if str(self) == str(other):
            return True

    def __str__(self):
        string = ""
        for i in range(0, len(self.peers)):
            string += "Peer %d:" % (i + 1)
            string += str(self.peers[i])
            string += "\n"
        return string


class message_keepmealive:
    def __init__(self, net_id):
        self.header = message_header(net_id, [18, 18, 18], message_type(2), [0, 0])
        ip1 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:9df5:d11e")), 54000)
        ip2 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:18fb:4f64")), 54000)
        ip3 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:405a:48c2")), 54000)
        ip4 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:9538:2eec")), 54000)
        ip5 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:2e04:4970")), 54000)
        ip6 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:68cd:cd53")), 54000)
        ip7 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:b3a2:bdef")), 54000)
        ip8 = peer_address(ipv6addresss(ipaddress.IPv6Address("::ffff:74ca:6b61")), 54000)
        peer_list = [ip1, ip2, ip3, ip4, ip5, ip6, ip7, ip8]
        self.peers = peers(peer_list)

    def serialise(self):
        data = self.header.serialise_header()
        data += self.peers.serialise()
        return data

    def __str__(self):
        string = str(self.header)
        string += "\n" + str(self.peers)
        return string

    def __eq__(self, other):
        if str(self) == str(other):
            return True
        return False


class message_bulk_pull:
    def __init__(self, block_hash, net_id):
        self.header = message_header(net_id, [18, 18, 18], message_type(6), [0, 0])
        self.public_key = binascii.unhexlify(block_hash)

    def serialise(self):
        data = self.header.serialise_header()
        data += self.public_key
        data += (0).to_bytes(32, "big")
        return data


class block_send:
    def __init__(self, prev, dest, bal, sig, work):
        self.previous = prev
        self.destination = dest
        self.balance = bal
        self.signature = sig
        self.work = work
        self.ancillary = {
            "account": None,
            "next": None,
        }

    def get_account(self): return self.ancillary["account"]

    def get_previous(self): return self.previous

    def get_balance(self): return self.balance

    def hash(self):
        data = b"".join([
            self.previous,
            self.destination,
            self.balance
        ])
        return blake2b(data, digest_size=32).hexdigest().upper()

    def str_ancillary_data(self):
        if self.ancillary["account"] is not None:
            hexacc = binascii.hexlify(self.ancillary["account"]).decode("utf-8").upper()
            account = get_account_id(self.ancillary["account"])
        else:
            hexacc = None
            account = self.ancillary["account"]
        if self.ancillary["next"] is not None:
            next = binascii.hexlify(self.ancillary["next"]).decode("utf-8").upper()
        else:
            next = self.ancillary["next"]
        string = ""
        string += "Acc : %s\n" % hexacc
        string += "      %s\n" % account
        string += "Next: %s\n" % next
        return string


    def __str__(self):
        string = "------------- Block Send -------------\n"
        string += "Hash: %s\n" % self.hash()
        string += "Prev: %s\n" % binascii.hexlify(self.previous).decode("utf-8").upper()
        string += "Dest: %s\n" % binascii.hexlify(self.destination).decode("utf-8").upper()
        string += "      %s\n" % get_account_id(self.destination)
        string += "Bal:  %d\n" % int(self.balance.hex(), 16)
        string += "Sign: %s\n" % binascii.hexlify(self.signature).decode("utf-8").upper()
        string += "Work: %s\n" % binascii.hexlify(self.work).decode("utf-8").upper()
        return string


class block_receive:
    def __init__(self, prev, source, sig, work):
        self.previous = prev
        self.source = source
        self.signature = sig
        self.work = work
        self.ancillary = {
            "account": None,
            "next": None,
            "balance": None
        }

    def get_account(self): return self.ancillary["account"]

    def get_previous(self): return self.previous

    def get_balance(self): return self.ancillary["balance"]

# TODO: Remember to reverse the order of the work if you implement serialisation!
    def hash(self):
        data = b"".join([
            self.previous,
            self.source
        ])
        return blake2b(data, digest_size=32).hexdigest().upper()

    def str_ancillary_data(self):
        if self.ancillary["account"] is not None:
            hexacc = binascii.hexlify(self.ancillary["account"]).decode("utf-8").upper()
            account = get_account_id(self.ancillary["account"])
        else:
            hexacc = None
            account = self.ancillary["account"]
        if self.ancillary["next"] is not None:
            next = binascii.hexlify(self.ancillary["next"]).decode("utf-8").upper()
        else:
            next = self.ancillary["next"]
        string = ""
        string += "Acc : %s\n" % hexacc
        string += "      %s\n" % account
        string += "Next: %s\n" % next
        return string


    def __str__(self):
        string = "------------- Block Receive -------------\n"
        string += "Hash: %s\n" % self.hash()
        string += "Prev: %s\n" % binascii.hexlify(self.previous).decode("utf-8").upper()
        string += "Src:  %s\n" % binascii.hexlify(self.source).decode("utf-8").upper()
        string += "Sign: %s\n" % binascii.hexlify(self.signature).decode("utf-8").upper()
        string += "Work: %s\n" % binascii.hexlify(self.work).decode("utf-8").upper()

        return string


class block_open:
    def __init__(self, source, rep, account, sig, work):
        self.source = source
        self.representative = rep
        self.account = account
        self.signature = sig
        self.work = work
        self.ancillary = {
            "previous": None,
            "next": None,
            "balance": None
        }

    def get_previous(self): return self.source

    def get_account(self): return self.account

    def get_balance(self): return self.ancillary["balance"]

    def hash(self):
        data = b"".join([
            self.source,
            self.representative,
            self.account
        ])
        return blake2b(data, digest_size=32).hexdigest().upper()

    def str_ancillary_data(self):
        if self.ancillary["previous"] is not None:
            previous = binascii.hexlify(self.ancillary["previous"]).decode("utf-8").upper()
        else:
            previous = self.ancillary["previous"]
        if self.ancillary["next"] is not None:
            next = binascii.hexlify(self.ancillary["next"]).decode("utf-8").upper()
        else:
            next = self.ancillary["next"]
        string = ""
        string += "Prev: %s\n" % previous
        string += "Next: %s\n" % next
        return string

    def __str__(self):
        hexacc = binascii.hexlify(self.account).decode("utf-8").upper()
        string = "------------- Block Open -------------\n"
        string += "Hash: %s\n" % self.hash()
        string += "Src:  %s\n" % binascii.hexlify(self.source).decode("utf-8").upper()
        string += "Repr: %s\n" % binascii.hexlify(self.representative).decode("utf-8").upper()
        string += "Acc : %s\n" % hexacc
        string += "      %s\n" % get_account_id(self.account)
        string += "Sign: %s\n" % binascii.hexlify(self.signature).decode("utf-8").upper()
        string += "Work: %s\n" % binascii.hexlify(self.work).decode("utf-8").upper()
        return string

    def __eq__(self, other):
        try:
            if self.source != other.source:
                return False
            elif self.representative != other.representative:
                return False
            elif self.account != other.account:
                return False
            elif self.signature != other.signature:
                return False
            elif self.work != other.work:
                return False
        except AttributeError:
            return False
        return True


class block_change:
    def __init__(self, prev, rep, sig, work):
        self.previous = prev
        self.representative = rep
        self.signature = sig
        self.work = work
        self.ancillary = {
            "account": None,
            "next": None,
            "balance": None
        }

    def get_account(self): return self.ancillary["account"]

    def get_previous(self): return self.previous

    def get_balance(self): return self.ancillary["balance"]

    def hash(self):
        data = b"".join([
            self.previous,
            self.representative
        ])
        return blake2b(data, digest_size=32).hexdigest().upper()

    def str_ancillary_data(self):
        if self.ancillary["account"] is not None:
            hexacc = binascii.hexlify(self.ancillary["account"]).decode("utf-8").upper()
            account = get_account_id(self.ancillary["account"])
        else:
            hexacc = None
            account = self.ancillary["account"]
        if self.ancillary["next"] is not None:
            next = binascii.hexlify(self.ancillary["next"]).decode("utf-8").upper()
        else:
            next = self.ancillary["next"]
        string = ""
        string += "Acc : %s\n" % hexacc
        string += "      %s\n" % account
        string += "Next: %s\n" % next
        return string

    def __str__(self):
        string = "------------- Block Change -------------\n"
        string += "Hash: %s\n" % self.hash()
        string += "Prev: %s\n" % binascii.hexlify(self.previous).decode("utf-8").upper()
        string += "Repr: %s\n" % binascii.hexlify(self.representative).decode("utf-8").upper()
        string += "Sign: %s\n" % binascii.hexlify(self.signature).decode("utf-8").upper()
        string += "Work: %s\n" % binascii.hexlify(self.work).decode("utf-8").upper()


class block_state:
    def __init__(self, account, prev, rep, bal, link, sig, work):
        self.account = account
        self.previous = prev
        self.representative = rep
        self.balance = bal
        self.link = link
        self.signature = sig
        self.work = work
        self.ancillary = {
            "next": None
        }

    def get_previous(self): return self.previous

    def get_account(self): return self.account

    def get_balance(self): return self.balance

    def hash(self):
        STATE_BLOCK_HEADER_BYTES = (b'\x00' * 31) + b'\x06'
        data = b"".join([
            STATE_BLOCK_HEADER_BYTES,
            self.account,
            self.previous,
            self.representative,
            self.balance,
            self.link

        ])
        return blake2b(data, digest_size=32).hexdigest().upper()

    def str_ancillary_data(self):
        if self.ancillary["next"] is not None:
            next = binascii.hexlify(self.ancillary["next"]).decode("utf-8").upper()
        else:
            next = self.ancillary["next"]
        string = "Next: %s" % next
        return string

    def __str__(self):
        hexacc = binascii.hexlify(self.account).decode("utf-8").upper()
        string = "------------- Block State -------------\n"
        string += "Hash: %s\n" % self.hash()
        string += "Acc:  %s\n" % hexacc
        string += "      %s\n" % get_account_id(self.account)
        string += "Prev: %s\n" % binascii.hexlify(self.previous).decode("utf-8").upper()
        string += "Repr: %s\n" % binascii.hexlify(self.representative).decode("utf-8").upper()
        string += "Bal:  %d\n" % int(self.balance.hex(), 16)
        string += "Link: %s\n" % binascii.hexlify(self.link).decode("utf-8").upper()
        string += "Sign: %s\n" % binascii.hexlify(self.signature).decode("utf-8").upper()
        string += "Work: %s\n" % binascii.hexlify(self.work).decode("utf-8").upper()
        return string

def read_socket(socket, bytes):
    data = b''
    while len(data) != bytes:
        data += socket.recv(1)
    return data


def read_block_send(s):
    data = read_socket(s, 152)
    block = block_send(data[:32], data[32:64], data[64:80], data[80:144], data[144:][::-1])
    return block


def read_block_receive(s):
    data = read_socket(s, 136)
    block = block_receive(data[:32], data[32:64], data[64:128], data[128:][::-1])
    return block


def read_block_open(s):
    data = read_socket(s, 168)
    block = block_open(data[:32], data[32:64], data[64:96], data[96:160], data[160:][::-1])
    return block


def read_block_change(s):
    data = read_socket(s, 136)
    block = block_change(data[:32], data[32:64], data[64:128], data[128:][::-1])
    return block


def read_block_state(s):
    data = read_socket(s, 216)
    block = block_state(data[:32], data[32:64], data[64:96], data[96:112], data[112:144], data[144:208],
                        data[208:])
    return block


def read_blocks_from_socket(s):
    blocks = []
    while True:
        block_type = s.recv(1)
        if len(block_type) == 0:
            print('socket closed by peer')
            break

        if block_type[0] == block_type_enum.send:
            block = read_block_send(s)
        elif block_type[0] == block_type_enum.receive:
            block = read_block_receive(s)
        elif block_type[0] == block_type_enum.open:
            block = read_block_open(s)
        elif block_type[0] == block_type_enum.change:
            block = read_block_change(s)
        elif block_type[0] == block_type_enum.state:
            block = read_block_state(s)
        elif block_type[0] == block_type_enum.invalid:
            print('received block type invalid')
            break
        elif block_type[0] == block_type_enum.not_a_block:
            print('received block type not a block')
            break
        else:
            print('received unknown block type %s' % block_type_enum[0])
            break
        blocks.append(block)
    return blocks


def pow_validate(work, prev):
    # It didn't want to create bytearrays with the raw bytes so I had to use the list()
    work = bytearray(list(work))
    prev = bytearray(list(prev))
    h = blake2b(digest_size=8)
    work.reverse()
    h.update(work)
    h.update(prev)
    final = bytearray(h.digest())
    final.reverse()
    return final > b'\xFF\xFF\xFF\xC0\x00\x00\x00\x00'


def verify(hash, signature, public_key=b'\xe8\x92\x08\xdd\x03\x8f\xbb&\x99\x87h\x96!\xd5"\x92\xae\x9c5\x94\x1at\x84un\xcc\xed\x92\xa6P\x93\xba'):
    try:
        ed25519_blake2.checkvalid(signature, hash, public_key)
    except ed25519_blake2.SignatureMismatch:
        return False
    return True


def verify_pow(block):
    if isinstance(block, block_open):
        return pow_validate(block.work, block.source)
    else:
        return pow_validate(block.work, block.previous)


def valid_block(block):
    work_valid = verify_pow(block)
    sig_valid = verify(binascii.unhexlify(block.hash()), block.signature, block.get_account())
    return work_valid and sig_valid


class blocks_manager:
    def __init__(self):
        #TODO: Remember to validate blocks!
        self.accounts = []
        self.processed_blocks = []
        self.unprocessed_blocks = []
        self.genesis_block = None
        self.create_genesis_account()

    def create_genesis_account(self):
        open_block = block_open(genesis_block_open["source"], genesis_block_open["representative"],
                                genesis_block_open["account"], genesis_block_open["signature"],
                                genesis_block_open["work"])
        open_block.ancillary["balance"] = genesis_block_open["balance"]
        genesis_account = nano_account(open_block)
        self.accounts.append(genesis_account)
        self.processed_blocks.append(open_block)
        self.genesis_block = open_block

    def process(self, block):
        successful = False
        if isinstance(block, block_open):
            successful = self.process_block_open(block)
        else:
            successful = self.process_block(block)

        if successful:
            self.process_unprocessed_blocks()

    def process_block_open(self, block):
        if not valid_block(block):
            return False
        if block.account == genesis_block_open["account"]:
            assert (block == self.genesis_block)
            self.processed_blocks.append(block)
            return True
        else:
            if not self.account_exists(block.get_account()):
                account = nano_account(block)
                self.accounts.append(account)
                self.processed_blocks.append(block)
                return True
            else:
                raise ProcessingErrorAccountAlreadyOpen()

    def process_block(self, block):
        account_pk = self.find_blocks_account(block)
        if account_pk is not None:
            block.ancillary["account"] = account_pk
            if not valid_block(block):
                return False
            self.find_prev_block(block).ancillary["next"] = binascii.unhexlify(block.hash())
        else:
            self.unprocessed_blocks.append(block)
            return False
        n_account = self.find_nano_account(account_pk)
        if n_account is not None:
            n_account.add_block(block)
        else:
            self.unprocessed_blocks.append(block)
            return False
        self.processed_blocks.append(block)
        return True

    def account_exists(self, account):
        for a in self.accounts:
            if a.account == account:
                return True
        return False

    def find_blocks_account(self, block):
        for b in self.processed_blocks:
            if b.hash() == binascii.hexlify(block.get_previous()).decode("utf-8").upper():
                assert(b.get_account() is not None)
                return b.get_account()
        return None

    def find_nano_account(self, account_pk):
        for a in self.accounts:
            if a.account == account_pk:
                return a
        return None

    def process_unprocessed_blocks(self):
        for i in range(0, len(self.unprocessed_blocks)):
            self.process(self.unprocessed_blocks.pop(0))

    def find_prev_block(self, block):
        hash = binascii.hexlify(block.get_previous()).decode("utf-8").upper()
        for b in self.processed_blocks:
            if b.hash() == hash:
                return b

class nano_account:
    def __init__(self, open_block):
        self.account = open_block.get_account()
        self.blocks = [open_block]

    def add_block(self, block):
        # TODO: Block processing required
        self.blocks.append(block)

    # This method is used for debugging: checking order
    def traverse_backwards(self):
        block = self.blocks[-1]
        traversal = []
        while block is not None:
            traversal.append(self.blocks.index(block))
            block = self.find_prev(block)
        return traversal

    # This method is used for debugging: checking order
    def traverse_forwards(self):
        block = self.blocks[0]
        traversal = []
        while block is not None:
            traversal.append(self.blocks.index(block))
            block = self.find_next(block)
        return traversal

    def find_prev(self, block):
        for b in self.blocks:
            if b.hash() == binascii.hexlify(block.get_previous()).decode("utf-8").upper():
                return b
        return None

    def find_next(self, block):
        if block.ancillary["next"] is None:
            return None
        for b in self.blocks:
            if b.hash() == binascii.hexlify(block.ancillary["next"]).decode("utf-8").upper():
                return b
        return None

    def str_blocks(self):
        string = ""
        for b in self.blocks:
            string += str(b)
        return string

    def __str__(self):
        string = "------------- Nano Account -------------\n"
        string += "Account: %s\n" % binascii.hexlify(self.account).decode("utf-8").upper()
        string += "       : %s\n" % get_account_id(self.account)
        string += "Blocks:  %d\n" % len(self.blocks)
        string += "Balance: %d\n" % int.from_bytes(self.blocks[-1].get_balance(), "big")
        return string



genesis_block_open = {
    "source": b'\xe8\x92\x08\xdd\x03\x8f\xbb&\x99\x87h\x96!\xd5"\x92\xae\x9c5\x94\x1at\x84un\xcc\xed\x92\xa6P\x93\xba',
    "representative": b'\xe8\x92\x08\xdd\x03\x8f\xbb&\x99\x87h\x96!\xd5"\x92\xae\x9c5\x94\x1at\x84un\xcc\xed\x92\xa6P\x93\xba',
    "account": b'\xe8\x92\x08\xdd\x03\x8f\xbb&\x99\x87h\x96!\xd5"\x92\xae\x9c5\x94\x1at\x84un\xcc\xed\x92\xa6P\x93\xba',
    "signature": b'\x9f\x0c\x93<\x8a\xde\x00M\x80\x8e\xa1\x98_\xa7F\xa7\xe9[\xa2\xa3\x8f\x86v@\xf5>\xc8\xf1\x80\xbd\xfe\x9e,\x12h\xde\xad|&d\xf3V\xe3z\xba6+\xc5\x8eF\xdb\xa0>R:{Z\x19\xe4\xb6\xeb\x12\xbb\x02',
    "work": b'b\xf0T\x17\xdd?\xb6\x91',
    "balance": (340282366920938463463374607431768211455).to_bytes(16, "big")
}

betactx = {
    'peeraddr': "peering-beta.nano.org",
    'peerport': 54000,
    'genesis_pub': '259A43ABDB779E97452E188BA3EB951B41C961D3318CA6B925380F4D99F0577A',
}

livectx = {
    'net_id': network_id(67),
    'peeraddr': "peering.nano.org",
    'peerport': 7075,
    'genesis_pub': 'E89208DD038FBB269987689621D52292AE9C35941A7484756ECCED92A65093BA',
    'random_block': '6E5404423E7DDD30A0287312EC79DFF5B2841EADCD5082B9A035BCD5DB4301B6'
}






ctx = livectx
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
peeraddr = random.choice(get_all_dns_addresses(ctx['peeraddr']))
s.connect((peeraddr, ctx['peerport']))
print('Connected to %s:%s' % s.getpeername())
s.settimeout(2)

keepalive = message_keepmealive(ctx['net_id'])
req = keepalive.serialise()
s.send(req)
bulk_pull = message_bulk_pull(ctx['genesis_pub'], network_id(67))
req = bulk_pull.serialise()
s.send(req)

blocks = read_blocks_from_socket(s)
blocks = blocks[::-1]
print(blocks)
manager = blocks_manager()
while len(blocks) != 0:
    manager.process(blocks.pop())

print(manager.accounts[0])
#TODO: Implement functions to print every objects state at any time
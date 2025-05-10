#!/usr/bin/env python3
import hashlib
import os
import sys
import time
from socket import socket
from urllib.request import Request, urlopen
from json import loads
from multiprocessing import cpu_count, Process

try:
    import libducohasher
    fasthash_supported = True
except ImportError:
    fasthash_supported = False

def current_time():
    return time.strftime("%H:%M:%S", time.localtime())

def fetch_pools():
    while True:
        try:
            print(f'{current_time()} : Fetching pool info...')
            headers = {'User-Agent': 'DuinoMiner/1.0'}
            req = Request("https://server.duinocoin.com/getPool", headers=headers)
            response = loads(urlopen(req).read().decode())
            return response["ip"], response["port"]
        except Exception as e:
            print(f'{current_time()} : Error fetching pool info: {e}, retrying in 15s')
            time.sleep(15)

def connect_to_pool():
    while True:
        try:
            ip, port = fetch_pools()
            print(f'{current_time()} : Connecting to {ip}:{port}')
            soc = socket()
            soc.connect((str(ip), int(port)))
            print(f'{current_time()} : Connected to pool server')
            server_version = soc.recv(100).decode()
            print(f'{current_time()} : Server Version: {server_version}')
            return soc
        except Exception as e:
            print(f'{current_time()} : Connection error: {e}, retrying in 10s')
            time.sleep(10)

def ducos1_fasthash(job_id, expected_hash, difficulty):
    time_start = time.time()
    hasher = libducohasher.DUCOHasher(bytes(job_id, encoding='ascii'))
    nonce = hasher.DUCOS1(bytes.fromhex(expected_hash), int(difficulty), 0)
    elapsed = time.time() - time_start
    hashrate = nonce / elapsed if elapsed > 0 else 0
    return nonce, hashrate

def ducos1_python(job_id, expected_hash, difficulty):
    time_start = time.time()
    base_hash = hashlib.sha1(job_id.encode('ascii'))
    for nonce in range(100 * int(difficulty) + 1):
        temp_hash = base_hash.copy()
        temp_hash.update(str(nonce).encode('ascii'))
        if temp_hash.hexdigest() == expected_hash:
            elapsed = time.time() - time_start
            hashrate = nonce / elapsed if elapsed > 0 else 0
            return nonce, hashrate
    return 0, 0

def mine(username, mining_key, UseLowerDiff, thread_id):
    while True:
        try:
            soc = connect_to_pool()
            while True:
                job_difficulty = "LOW" if UseLowerDiff else "MEDIUM"
                job_request = f"JOB,{username},{job_difficulty},{mining_key}"
                soc.send(job_request.encode("utf8"))

                job = soc.recv(1024).decode().rstrip("\n").split(",")
                if len(job) < 3:
                    print(f'{current_time()} : Invalid job format from server.')
                    break

                job_id, expected_hash, difficulty = job

                if fasthash_supported:
                    nonce, hashrate = ducos1_fasthash(job_id, expected_hash, difficulty)
                else:
                    nonce, hashrate = ducos1_python(job_id, expected_hash, difficulty)

                result_packet = f"{nonce},{hashrate},LiteDucoMiner{thread_id}"
                soc.send(result_packet.encode("utf8"))

                feedback = soc.recv(1024).decode().rstrip("\n")
                status = "Accepted" if feedback == "GOOD" else "Rejected"
                print(f': [T{thread_id}] {status} share {nonce} - {int(hashrate/1000)} kH/s (Diff {difficulty})')

        except Exception as e:
            print(f'{current_time()} : [T{thread_id}] Fatal error: {e}. Restarting in 5s...')
            time.sleep(5)

def main():
    username = input('Duino-Coin Username:\n> ')
    mining_key = input("Mining key? ['None' for no key]\n> ")
    diff_choice = input('Use lower difficulty? (Y/N) [Default: Y]\n> ')
    UseLowerDiff = not (diff_choice.lower() == "n")

    threads = input(f"How many threads to use? [1-{cpu_count()}] (default: {cpu_count()})\n> ")
    try:
        threads = int(threads)
    except:
        threads = cpu_count()

    threads = max(1, min(threads, cpu_count()))

    print(f"Starting {threads} mining thread(s)...")
    processes = []
    for i in range(threads):
        p = Process(target=mine, args=(username, mining_key, UseLowerDiff, i))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

if __name__ == "__main__":
    main()

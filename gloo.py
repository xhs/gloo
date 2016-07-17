#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import traceback
import functools
from urllib.parse import urlparse

import re
length_regex = re.compile(r'Content-Length: ([0-9]+)\r\n', re.IGNORECASE)

BUFFER_SIZE = 4096


async def handle_client(reader, writer, loop=None):
    header_str = ''
    payload = b''
    try:
        while True:
            line = await reader.readline()
            if not line or line == b'\r\n':
                break
            header_str += line.decode('utf-8')

        match = length_regex.search(header_str)
        if match:
            length = int(match.group(1))
            while len(payload) < length:
                payload += await reader.read(BUFFER_SIZE)

        headers = header_str.split('\r\n')[:-1]
        method, path, version = headers[0].split(' ')

        if method == 'CONNECT':
            host, port_str = path.split(':')
            port = int(port_str)
            rreader, rwriter = await asyncio.open_connection(host=host, port=port, loop=loop)
            writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            tasks = [
                asyncio.ensure_future(relay(reader, rwriter), loop=loop),
                asyncio.ensure_future(relay(rreader, writer), loop=loop)
            ]
            await asyncio.wait(tasks, loop=loop)
        else:
            r = urlparse(path)
            host = r.hostname
            port = r.port or 80
            new_headers = []
            new_headers.append(' '.join([method, r.path, version]))
            connection_header_found = False
            for header in headers[1:]:
                name, value = header.strip().split(': ', 1)
                if name.lower() == 'proxy-connection':
                    continue
                elif name.lower() == 'connection':
                    connection_header_found = True
                    new_headers.append('Connection: close')
                else:
                    new_headers.append(header)
            if not connection_header_found:
                new_headers.append('Connection: close')
            new_headers.append('\r\n')
            new_header_str = '\r\n'.join(new_headers)

            rreader, rwriter = await asyncio.open_connection(host=host, port=port, loop=loop)
            rwriter.write(new_header_str.encode('utf-8'))
            if payload:
                rwriter.write(payload)
            await rwriter.drain()

            while True:
                data = await rreader.read(BUFFER_SIZE)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
    except:
        traceback.print_exc()
    finally:
        writer.close()


async def relay(reader, writer):
    try:
        while True:
            data = await reader.read(BUFFER_SIZE)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except:
        traceback.print_exc()
    finally:
        writer.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        callback = functools.partial(handle_client, loop=loop)
        loop.run_until_complete(asyncio.start_server(callback, host='127.0.0.1', port=5000, loop=loop))
        loop.run_forever()
    except KeyboardInterrupt:
        print('Closing...')
    finally:
        loop.close()

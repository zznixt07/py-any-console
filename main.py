from __future__ import annotations

# typehint only
from typing import Optional, Pattern, Tuple, List, Dict, Union
from asyncio.events import AbstractEventLoop
from asyncio.futures import Future
from asyncio.tasks import Task
from http.cookiejar import Cookie
from aiohttp.client_ws import ClientWebSocketResponse
from aiohttp.http_websocket import WSMessage
from aiohttp import WSMsgType

import re
import random
import asyncio
from asyncio.exceptions import CancelledError
import json
import logging
from datetime import datetime
from aiohttp import ClientSession
import aioconsole
from py_any import PythonAnywhereApi, PythonAnywhere


KBD_INTRPT: bool = False                         # cannot NOT use global
GatheringAwaitable = Future
logger: logging.Logger = logging.getLogger(__name__)

def get_socket_url(html: str) -> str:
    console_hostname: str = re.search(r"Anywhere\.LoadConsole\((.+?),", html) \
                                .group(1).strip("'").strip('"')

    characters: Tuple[str, ...] = tuple('abcdefghijklmnopqrstuvwxyz0123456789_')
    rand_string: str = ''.join([random.choice(characters) for _ in range(8)])
    rand_num: int = random.randint(0, 999) 

    return f'wss://{console_hostname}/sj/{rand_num}/{rand_string}/websocket'

def send_string(strings: str) -> str:
    return '["' + strings + '\\r\\n' + '"]'

async def prompt_and_send(ws: ClientWebSocketResponse) -> None:
    while True:
        new_msg_to_send: str = await aioconsole.ainput('$ ')
        if new_msg_to_send == 'bye':
            print('\nExiting...')
            await ws.close()    # triggers .receive() in func<receive_output>.
            break
        await ws.send_str(send_string(new_msg_to_send))

async def receive_output(ws: ClientWebSocketResponse) -> None:
    hex_val: str = '\u001b' # this will originally have 2 backslashes, but since it's
                            # used on json.loads()'s output, only one backslash needed
    hexes: Pattern = re.compile(fr'{hex_val}\[.*?m')
    while True:
        output: WSMessage = await ws.receive()
        if output.type == WSMsgType.TEXT:
            received: str = output.data
            if received[0] == 'a':
                # first strip the char 'a'.
                # ignore characters `["` and `"]` from left & right resp.
                # cleaned_data = received.lstrip('a')[2:-2].replace('\\r\\n', '\n')
                # unic = re.compile(r'\\u....')
                # cleaned_data = unic.sub('', cleaned_data)

                cleaned_data: str = json.loads(received.lstrip('a'))[0]
                if cleaned_data.startswith(hex_val):
                    print(hexes.sub('', cleaned_data), end='', flush=True)
                else:
                    print(cleaned_data, end='', flush=True)

        elif output.type in (WSMsgType.ERROR, WSMsgType.CLOSED):
            print(output)
            if KBD_INTRPT:      # KeyboardInterrupt cannot await .sleep() cuz
                                # event loop is already closed
                break           # break to prevent executing below stmt.
            
            # required to allow breaking out of while loop from func<prompt_and_send>
            # then return back and break this loop
            await asyncio.sleep(0.05)
            break

async def initiate_conn(
    ws: ClientWebSocketResponse,
    url: str,
    session_cookie: str,
    console_id: int,
    starting_commands: Optional[List[str]]
    ) -> None:

    starting_hex: str = '\\u001b'
    input_string: str = 'a["' + starting_hex

    await ws.receive()                       # server sends first message 'o'
    await ws.send_str(f'["{starting_hex}[{session_cookie};{console_id};;a"]')
    # just discard the first couple messages cuz it contains prev history
    # and may contain other info
    second_msg_obj: WSMessage  = await ws.receive()
    if 'tarpit' in second_msg_obj.data:
        print('In Tarpit. Starting Slowly...')
        await ws.receive()                   # tarpit receives n+1 more messages.
    history: WSMessage = await ws.receive()  # either has history or is empty-ish

    # if history is not present, then the console has reset or is just starting.
    # it will take some time, wait for it to send the input strings.
    if history.data == 'a[""]':
        msg_obj: WSMessage = await ws.receive()
        while not msg_obj.data.startswith(input_string):
            msg_obj = await ws.receive()
    
    print('Connected Successfully. (Type `bye` to exit)')
    print(datetime.utcnow().strftime('%H:%M'), ' ', end='', flush=True)

    if starting_commands:
        tasks: GatheringAwaitable = asyncio.gather(*[
            ws.send_str(send_string(cmd)) for cmd in starting_commands
        ])
        await tasks

    task_terminal: Task[None] = asyncio.create_task(prompt_and_send(ws))
    task_recv: Task[None] = asyncio.create_task(receive_output(ws))
    await task_terminal
    await task_recv
    
    # threading.Thread(target=ask_for_input, args=[ws]).start()
            
# def ask_for_input(ws):
#     cmd = '["' + input('~ $ ') + '"]'
#     curr_loop = asyncio.get_running_loop()
#     curr_loop.run_until_complete(ws.send_str(cmd))

async def close_socket(ws: ClientWebSocketResponse) -> None:
    await ws.close()
    print(await ws.receive())

async def main(
        username: str,
        password: str,
        api_token: str,
        starting_commands: List[str] = None
    ) -> None:
    # get sessionid cookie first by logging in. 
    session_cookie_val: str = ''
    pyany_browser: PythonAnywhere = PythonAnywhere(
        username, password, fresh_login=False
    )
    if not pyany_browser.is_logged_in:
        raise ValueError('Incorrect Credentials.')
    cookie: Cookie
    for cookie in pyany_browser.sess.cookies:
        if cookie.name == 'sessionid':
            session_cookie_val = cookie.value

    # get list of consoles
    pyany_api: PythonAnywhereApi = PythonAnywhereApi(username, api_token)
    Console = Dict[str, Union[int, str]]
    consoles: List[Console] = pyany_api.get_consoles()
    console: Console = {}
    try:
        console = consoles[0]
    except IndexError:
        print('No console available. Creating new..')
        console = pyany_api.create_console()

    print(f"Console on HTTP URL: {PythonAnywhereApi.origin}{console['console_url']}")
    console_id: int = console['id']
    console_frame_url: str = console['console_frame_url']
    logger.debug('console id: %d\nconsole frame url: %s', console_id, console_frame_url)
    logger.debug('session: %s', pyany_browser.sess.cookies)
    html: str = pyany_browser.sess.get(PythonAnywhere.origin + console_frame_url).text
    url: str = get_socket_url(html)
    print('Console on WSS URL:', url, '\n')

    session: ClientSession
    ws: ClientWebSocketResponse
    async with ClientSession() as session:
        async with session.ws_connect(url) as ws:
            try:
                await initiate_conn(ws, url, session_cookie_val, console_id, starting_commands)
            except (KeyboardInterrupt, CancelledError) as e:
                import sys
                global KBD_INTRPT
                KBD_INTRPT = True

                print(sys.exc_info())
                print('\n\nExiting....')
                await close_socket(ws)
    
async def shutdown(tasks: GatheringAwaitable) -> None:
    tasks.cancel()
    try:
        await tasks
    except asyncio.CancelledError:
        pass

if __name__ == '__main__':
    logging.basicConfig(level=10)
    logging.disable()

    commands: List[str] = ['ls', 'date']
    cred: Tuple[str, str, str]
    cred = ('USERNAME', 'PASSWORD', 'APITOKEN')

    print('Account:', cred[0])
    loop: AbstractEventLoop = asyncio.get_event_loop()
    gathered: GatheringAwaitable = asyncio.gather(main(*cred, starting_commands=commands))
    try:
        loop.run_until_complete(gathered)
    except KeyboardInterrupt: # KeyboardInterrupt exception is reraised. dunno why.
        # Changed in version 3.7: If the gather itself is cancelled,
        # the cancellation is propagated regardless of return_exceptions.
        # gathered.cancel()
        loop.run_until_complete(shutdown(gathered))
    finally:
        loop.run_until_complete(asyncio.sleep(0.7))
        loop.close()

    
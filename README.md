## CLI Client for PythonAnywhere's Browser Console
This script saves you the hassle to connect to your accounts console in [pythonanywhere.com](https://www.pythonanywhere.com/). Uses asynchronous websockets. 
![console](https://github.com/zznixt07/py-any-console/blob/main/example.png?raw=true)
### Requirements
- aiohtttp
- aioconsole
- py_any (https://gitlab.com/zznixt07/py-any)
### Installation
- Download a zip of this repo. Go inside the downloaded repo.
- Run `pip install -r requirements.txt`
### Usage
- Inside `main.py`. At the bottom, enter your pythonanywhere's username, password and api token (your token is [here](https://www.pythonanywhere.com/account/#api_token))
- Run `main.py`. Done. 
- Type `bye` to exit or use Ctrl + c.

The entry function is `main` function inside `main.py` and it accepts username, password, token and optionally a list of commands to run after the console is ready to accept input.
```
commands: List[str] = ['ls', 'date'] # empty list to not run any commands.
cred: Tuple[str, str, str]
cred = ('Your username', 'Your password', 'Your api token')

loop = asyncio.get_event_loop()
gathered = asyncio.gather(main(*cred, starting_commands=commands))
try:
	loop.run_until_complete(gathered)
except  KeyboardInterrupt:
	loop.run_until_complete(shutdown(gathered))
finally:
	loop.run_until_complete(asyncio.sleep(0.7))
	loop.close()
```
# TODOs
- Parse prefix msgs more nicely.
# 3. Dev environment with paramiko

The PC has **no `sshpass` and no `expect`**. Use **paramiko** for everything:
SSH exec, SFTP up/down, long-running scripts. Assume code is authored locally
and pushed to the board; `/root/...` on the board is *not* your working dir.

```bash
pip install paramiko    # if missing
```

## Canonical client

```python
import paramiko

BOARD = "10.1.2.3"
USER, PASS = "root", "dfrobot"

def client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(BOARD, username=USER, password=PASS, timeout=10)
    return c

def run(c, cmd, t=20):
    """Run a command; always return stdout+stderr together."""
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace") + se.read().decode(errors="replace")
```

`run` returning both streams is deliberate: pinpong prints its banner to stdout
and ALSA errors to stderr, and you usually want both to judge "did it start".

## Deploy a file

```python
c = client()
c.open_sftp().put("examples/04_push_to_talk_stt.py",
                  "/root/g-buddy/04_push_to_talk_stt.py")
c.close()
```

SFTP `get` fetches results back:

```python
c.open_sftp().get("/tmp/frame.png", "frame.png")
```

## Deploy-and-run recipe (the standard workflow)

"Deploy" means **push → kill stale → launch in the background → leave running**.
Do not kill it unless asked to stop.

```python
import time, paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.1.2.3", username="root", password="dfrobot", timeout=10)

def run(cmd, t=20):
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace") + se.read().decode(errors="replace")

c.open_sftp().put("app.py", "/root/app.py")
run("pkill -KILL -f 'python app.py'; sleep 1", 5)
run("cd /root && (python app.py > /tmp/app.out 2> /tmp/app.err &)", 5)
time.sleep(4)                                   # let it boot / load models
print(run("cat /tmp/app.out; echo ---; cat /tmp/app.err", 10))
c.close()
```

**Why the subshell `( … &)`:** a bare `cmd &` can leave `exec_command` waiting
and raise `PipeTimeout` even though the app started. The parens detach it.

**Set `DISPLAY=:0`** for anything that draws to the screen when launched from a
non-interactive SSH shell:

```bash
cd /root && export DISPLAY=:0 && (python3 app.py > /tmp/app.out 2> /tmp/app.err &)
```

## Stop a running script

SIGINT first — the `unihiker` library installs a graceful `exit_handler` that
releases the framebuffer/GPIO; then SIGKILL as a fallback:

```python
run("pkill -INT -f 'python app.py'; sleep 1; pkill -KILL -f 'python app.py'", 5)
```

## `pkill -f` self-match trap

`pkill -f 'python app.py'` also matches the `sh -c` command line running it, so
the session can kill itself or hang. Use the **bracket trick**:

```bash
pkill -KILL -f '[p]ython app.py'
```

Same for checks: `pgrep -af '[a]pp.py'`, `ps aux | grep '[a]pp.py' | wc -l`.

## Checking it is really running (and only once)

```bash
pgrep -af app.py | grep -v pgrep        # expect exactly one line
awk '/VmRSS/{print $2/1024 " MB"}' /proc/<pid>/status   # RAM headroom (512 MB!)
```

Two copies of a GUI script draw overlapping windows on the same display →
nonsensical screenshots. Always check for duplicates after launching.

## Logs and the buffering trap

Python **block-buffers stdout when redirected**, so `print()`s do not appear in
`/tmp/app.out` until the buffer flushes or the process exits cleanly.

- `python3 -u app.py` — but a script that `os.execv`s itself (the Vosk
  `LD_PRELOAD` ABI restart) **loses the `-u` flag**.
- Prefer the environment variable, which survives `execv`:
  `PYTHONUNBUFFERED=1 python3 app.py`.
- **stderr is unbuffered** — check `/tmp/app.err` first for crashes.
- Sending SIGINT usually flushes stdout (clean shutdown), so the log fills in
  after a graceful stop.

## Screenshots (verify a GUI you cannot see)

Upload the snapshot script once, run it, pull the PNG. See `m10-api.md` for the
RGB565 decode snippet. Shape:

```python
c = client()
c.open_sftp().put("snap.py", "/tmp/snap.py")
run(c, "python3 /tmp/snap.py", 30)              # writes /tmp/frame.png on board
c.open_sftp().get("/tmp/frame.png", "frame.png")
```

Then verify programmatically: colour census (count pixels), ASCII-art render, or
frame diffing. Pitfalls: skip-loop tearing, reading during an animation, and the
GUI↔framebuffer rotation mapping under landscape mode (`m10-api.md` §7 and
`verify-gui.md`).

## Gotchas checklist

- `timeout=10` on `connect` — the board is sometimes still booting.
- GUI scripts never exit on their own; run them in the background and poll.
- `exec_command` timeouts raise `PipeTimeout` — treat it as "still running",
  not "failed".
- Close the client (`c.close()`) when done; leaked sessions accumulate.
- Paths: the board's own scratch space is `/tmp`; the repo's deploy target has
  conventionally been `/root/g-buddy/`.

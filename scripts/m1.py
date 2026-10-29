"""Native Windows M1 setup/lifecycle. Run from the repository with Python 3.11.

No global PATH, service, model, or firewall changes. Secrets stay in runtime/.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR, RUN = ROOT / "vendor", ROOT / "runtime"
RA, OK = VENDOR / "rathena", VENDOR / "openkore"
DB = VENDOR / "mariadb" / "bin"
PERL = VENDOR / "strawberry-perl"
PINS = json.loads((ROOT / "config/versions.json").read_text())
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def env_perl():
    env = os.environ.copy()
    env.update(LANG="C", LC_ALL="C", LC_CTYPE="C")
    # Exclude unrelated MinGW installations from compiler/DLL resolution.
    env["PATH"] = os.pathsep.join(str(PERL / p) for p in
        ("perl/site/bin", "perl/bin", "c/bin")) + os.pathsep + os.environ["SystemRoot"] + "\\system32"
    return env


def run(args, *, cwd=ROOT, env=None, data=None, log=None):
    with open(log, "wb") if log else open(os.devnull, "wb") as out:
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
            input=data, stdout=out if log else None, stderr=subprocess.STDOUT,
            creationflags=FLAGS)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} exited {result.returncode}; log: {log}")


def available(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_port(port, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.3):
                return
        except OSError:
            time.sleep(.25)
    raise TimeoutError(f"127.0.0.1:{port} did not open")


def acquire():
    if shutil.disk_usage(ROOT).free < 8 * 1024**3:
        raise RuntimeError("Reserve at least 8 GiB before setup")
    for name in ("rathena", "openkore"):
        dest = VENDOR / name
        if not dest.exists():
            run(["git", "clone", "--no-checkout", "--filter=blob:none", PINS[name]["url"], dest])
            run(["git", "-C", dest, "checkout", PINS[name]["commit"]])
        head = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
        if head != PINS[name]["commit"]:
            raise RuntimeError(f"Refusing to replace existing {name} revision {head}")
    for name, folder in (("mariadb", "mariadb"), ("strawberry", "strawberry-perl")):
        archive = VENDOR / "downloads" / f"{name}.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            urllib.request.urlretrieve(PINS[name]["url"], archive)
        if hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != PINS[name]["sha256"]:
            raise RuntimeError(f"{name} checksum mismatch")
        if not (VENDOR / folder).exists():
            with zipfile.ZipFile(archive) as z:
                z.extractall(VENDOR if name == "mariadb" else VENDOR / folder)
            if name == "mariadb":
                (VENDOR / "mariadb-10.11.19-winx64").rename(VENDOR / folder)


def build():
    write(RA / "src/custom/defines_pre.hpp", "#pragma once\n#define PRERE\n#define PACKETVER 20130807\n")
    write(RA / "src/custom/defines_post.hpp", "#pragma once\n#undef PACKET_OBFUSCATION\n#undef PACKET_OBFUSCATION_WARN\n")
    vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    vs = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
    run([Path(vs) / "MSBuild/Current/Bin/MSBuild.exe", "rAthena.sln",
        "/t:server-components\\login-server;server-components\\char-server;server-components\\map-server",
        "/p:Configuration=Release", "/p:Platform=x64", "/p:DefaultPlatformToolset=v142",
        "/p:WindowsTargetPlatformVersion=10.0.19041.0", "/m:2", "/nologo", "/verbosity:minimal"],
        cwd=RA, log=RUN / "logs/rathena-build.log")
    run([sys.executable, "src/scons-local-3.1.2/scons.py", "-j2"], cwd=OK,
        env=env_perl(), log=RUN / "logs/openkore-build.log")
    run([PERL / "perl/bin/perl.exe", "openkore.pl", "--version"], cwd=OK, env=env_perl())


def credentials():
    path = RUN / "secrets.json"
    if not path.exists():
        write(path, json.dumps({k: secrets.token_hex(10) for k in
            ("root", "db", "inter", "agent", "peer", "agent_token", "peer_token")}, indent=2))
    return json.loads(path.read_text())


def configure():
    c = credentials()
    write(RUN / "mariadb/my.ini", f"""[mysqld]
basedir={ (VENDOR / 'mariadb').as_posix() }
datadir={ (RUN / 'mariadb/data').as_posix() }
bind-address=127.0.0.1
port=3306
character-set-server=utf8mb4
innodb-buffer-pool-size=128M
max-connections=20
skip-name-resolve
""")
    write(RUN / "mariadb/root.ini", f"[client]\nuser=root\npassword={c['root']}\nhost=127.0.0.1\nport=3306\n")
    inter = "".join(f"{p}_{k}: {v}\n" for p in
        ("login_server", "char_server", "map_server", "web_server") for k, v in
        (("ip", "127.0.0.1"), ("id", "m1server"), ("pw", c["db"]), ("db", "ragnarok")))
    inter += f"ipban_db_id: m1server\nipban_db_pw: {c['db']}\nipban_db_db: ragnarok\nlog_db_id: m1server\nlog_db_pw: {c['db']}\nlog_db_db: ragnarok\nmysql_reconnect_type: 1\nmysql_reconnect_count: 2\n"
    write(RA / "conf/import/inter_conf.txt", inter)
    common = f"bind_ip: 127.0.0.1\nuserid: m1inter\npasswd: {c['inter']}\n"
    write(RA / "conf/import/login_conf.txt", "bind_ip: 127.0.0.1\nconsole: no\n")
    write(RA / "conf/import/char_conf.txt", common + "login_ip: 127.0.0.1\nchar_ip: 127.0.0.1\nserver_name: M1 Local\npincode_enabled: no\n")
    write(RA / "conf/import/map_conf.txt", common + "char_ip: 127.0.0.1\nmap_ip: 127.0.0.1\n")
    for who, port in (("agent", 8765), ("peer", 8766)):
        profile = RUN / "openkore" / who
        profile.mkdir(parents=True, exist_ok=True)
        config = (OK / "control/config.txt").read_text()
        replacements = {"master": "M1 Local", "server": "0", "username": f"m1{who}",
            "password": c[who], "char": "0", "attackAuto": "0", "route_randomWalk": "0",
            "itemsTakeAuto": "0", "itemsGatherAuto": "0", "teleportAuto_hp": "0",
            "secureAdminPassword": "0", "dcOnMaxReconnections": "3", "pauseCharLogin": "1", "portalCompile": "-1"}
        import re
        for key, value in replacements.items():
            config = re.sub(rf"(?m)^{key}(?:[ \t].*)?$", f"{key} {value}", config)
        write(profile / "config.txt", config)
        write(profile / "bridge.json", json.dumps({"agent_id": who, "port": port, "token": c[f"{who}_token"]}))
        (profile / "logs").mkdir(exist_ok=True)
        write(profile / "servers.txt", """[M1 Local]
ip 127.0.0.1
port 6900
version 30
master_version 1
serverType kRO_RagexeRE_2013_08_07a
serverEncoding Western
charBlockSize 144
addTableFolders kRO/RagexeRE_2013_08_07a;kRO
pinCode 0
""")
        write(profile / "sys.txt", "loadPlugins 2\nloadPlugins_list m1_bridge\nsendAnonymousStatisticReport 0\n")
        timeouts = (OK / "control/timeouts.txt").read_text()
        for key, value in (("reconnect", "5"), ("reconnect_backoff", "5,10,15"), ("reconnect_random", "0")):
            timeouts = re.sub(rf"(?m)^{key}\s+.*$", f"{key} {value}", timeouts)
        write(profile / "timeouts.txt", timeouts)


def launch(args, name, cwd=ROOT, env=None):
    # A private hidden console lets stop() deliver SIGINT to this process only.
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (RUN / f"logs/{name}.log").open("ab") as log:
        return subprocess.Popen([str(a) for a in args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)


def sql(data):
    run([DB / "mariadb.exe", f"--defaults-file={RUN / 'mariadb/root.ini'}"], data=data.encode())


def initialize():
    if (RUN / "mariadb/data").exists():
        raise RuntimeError("Data directory exists; initialization is one-time and never overwrites it")
    if not available(3306):
        raise RuntimeError("Port 3306 is occupied")
    c = credentials()
    run([DB / "mariadb-install-db.exe", f"--datadir={RUN / 'mariadb/data'}", "--port=3306"],
        log=RUN / "logs/mariadb-init.log")
    init = RUN / "mariadb/bootstrap.sql"
    write(init, f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{c['root']}';\n"
        f"ALTER USER 'root'@'127.0.0.1' IDENTIFIED BY '{c['root']}';\n"
        "DELETE FROM mysql.global_priv WHERE User='root' AND Host NOT IN ('localhost','127.0.0.1');\nFLUSH PRIVILEGES;\n")
    proc = launch([DB / "mariadbd.exe", f"--defaults-file={RUN / 'mariadb/my.ini'}", f"--init-file={init}"], "mariadb")
    try:
        wait_port(3306)
        sql("CREATE DATABASE ragnarok CHARACTER SET utf8mb4;\n")
        for name in ("main.sql", "web.sql", "roulette_default_data.sql", "logs.sql"):
            sql("USE ragnarok;\n" + (RA / "sql-files" / name).read_text(encoding="utf-8"))
        sql(f"""CREATE USER 'm1server'@'127.0.0.1' IDENTIFIED BY '{c['db']}';
GRANT SELECT,INSERT,UPDATE,DELETE ON ragnarok.* TO 'm1server'@'127.0.0.1';
USE ragnarok;
UPDATE login SET userid='m1inter',user_pass='{c['inter']}' WHERE account_id=1;
""")
        for who, aid, name, x in (("agent", 2000000, "M1 Agent", 150), ("peer", 2000001, "M1 Peer", 152)):
            sql(f"""USE ragnarok;
INSERT INTO login(account_id,userid,user_pass,sex,email) VALUES({aid},'m1{who}','{c[who]}','M','m1@localhost');
INSERT INTO `char`(account_id,char_num,name,class,base_level,job_level,str,agi,vit,`int`,dex,luk,max_hp,hp,max_sp,sp,last_map,last_x,last_y,save_map,save_x,save_y,sex)
VALUES({aid},0,'{name}',0,1,1,5,5,5,5,5,5,50,50,10,10,'prontera',{x},180,'prontera',{x},180,'M');
INSERT INTO inventory(char_id,nameid,amount,identify) SELECT char_id,501,3,1 FROM `char` WHERE account_id={aid};
""")
        write(RUN / "initialized.json", json.dumps({"rathena": PINS["rathena"]["commit"], "time": time.time()}))
    finally:
        run([DB / "mariadb-admin.exe", f"--defaults-file={RUN / 'mariadb/root.ini'}", "shutdown"])
        proc.wait(timeout=30)
        init.unlink(missing_ok=True)


def client_args(who):
    profile = RUN / "openkore" / who
    return [PERL / "perl/bin/perl.exe", f"-I{ROOT / 'bridge/lib'}", "openkore.pl", f"--control={profile};{OK / 'control'}",
        f"--tables={profile};{OK / 'tables'}", f"--logs={profile / 'logs'}",
        f"--plugins={ROOT / 'bridge/openkore'}", "--interface=M1Headless", "--ai=off"]


def start():
    if (RUN / "processes.json").exists():
        raise RuntimeError("Process registry exists; run status/stop before starting")
    for port in (3306, 6900, 6121, 5121, 8765, 8766):
        if not available(port):
            raise RuntimeError(f"Port {port} is occupied")
    processes = {}
    try:
        for name, port, args, cwd in [
            ("mariadb", 3306, [DB / "mariadbd.exe", f"--defaults-file={RUN / 'mariadb/my.ini'}"], ROOT),
            *[(f"{name}-server", port, [RA / f"{name}-server.exe"], RA) for name, port in
                (("login", 6900), ("char", 6121), ("map", 5121))]]:
            p = launch(args, name, cwd)
            processes[name] = {"pid": p.pid, "exe": str(args[0].resolve())}
            write(RUN / "processes.json", json.dumps(processes, indent=2))
            wait_port(port, 120)
        print("Server listeners ready on loopback. Start clients with: m1.py client agent|peer")
    except BaseException:
        stop()
        raise


def client(who):
    processes = json.loads((RUN / "processes.json").read_text())
    if who in processes:
        raise RuntimeError(f"{who} is already registered")
    env = env_perl()
    env["M1_BRIDGE_CONFIG"] = str(RUN / "openkore" / who / "bridge.json")
    p = launch(client_args(who), who, OK, env)
    processes[who] = {"pid": p.pid, "exe": str((PERL / "perl/bin/perl.exe").resolve())}
    write(RUN / "processes.json", json.dumps(processes, indent=2))
    print(f"Started {who}, PID {p.pid}")


def signal_console(pid):
    kernel = ctypes.windll.kernel32
    kernel.FreeConsole()
    if not kernel.AttachConsole(pid):
        raise OSError("Cannot attach to project process console")
    kernel.SetConsoleCtrlHandler(None, True)
    if not kernel.GenerateConsoleCtrlEvent(0, 0):
        raise OSError("Cannot send CTRL_C_EVENT")
    time.sleep(.2)
    kernel.FreeConsole()


def stop(only=None):
    registry = RUN / "processes.json"
    if not registry.exists():
        return
    # Windows verifies the executable path before signaling any recorded PID.
    processes = json.loads(registry.read_text())
    for name in reversed(processes):
        if only and name != only:
            continue
        info = processes[name]
        handle = ctypes.windll.kernel32.OpenProcess(0x1000 | 0x100000, False, info["pid"])
        if not handle:
            continue
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = ctypes.c_ulong(len(buf))
            if not ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                raise OSError("Cannot verify process path")
            if os.path.normcase(buf.value) != os.path.normcase(info["exe"]):
                raise RuntimeError(f"PID {info['pid']} no longer belongs to {name}")
            if name == "mariadb":
                run([DB / "mariadb-admin.exe", f"--defaults-file={RUN / 'mariadb/root.ini'}", "shutdown"])
            else:
                run([sys.executable, __file__, "signal", str(info["pid"])])
            if ctypes.windll.kernel32.WaitForSingleObject(handle, 30000) != 0:
                raise TimeoutError(f"{name} did not stop; registry retained")
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    remaining = {k: v for k, v in processes.items() if only and k != only}
    if remaining:
        write(registry, json.dumps(remaining, indent=2))
    else:
        registry.unlink()
    print(f"Stopped {only or 'project processes'}")


def restart_map():
    stop("map-server")
    # Acceptance fault: leave the game endpoint down for five seconds.
    time.sleep(5)
    processes = json.loads((RUN / "processes.json").read_text())
    p = launch([RA / "map-server.exe"], "map-server", RA)
    processes["map-server"] = {"pid": p.pid, "exe": str((RA / "map-server.exe").resolve())}
    write(RUN / "processes.json", json.dumps(processes, indent=2))
    wait_port(5121, 120)
    print("Map server restarted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "build", "configure", "initialize", "start", "stop", "status", "client", "signal", "restart-map"))
    parser.add_argument("target", nargs="?")
    a = parser.parse_args()
    (RUN / "logs").mkdir(parents=True, exist_ok=True)
    if a.command == "client":
        if a.target not in ("agent", "peer"):
            parser.error("client requires agent or peer")
        client(a.target)
    elif a.command == "signal":
        signal_console(int(a.target))
    elif a.command == "status":
        print((RUN / "processes.json").read_text() if (RUN / "processes.json").exists() else "Stopped")
    elif a.command == "restart-map":
        restart_map()
    else:
        globals()[a.command]()


if __name__ == "__main__":
    main()

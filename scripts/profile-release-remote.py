#!/usr/bin/env python3
"""Fixed-command publisher for the small claudiuschuster.de static root.

The production copy is installed outside the public document root and reached
only through a dedicated SSH key with a forced command.  The bootstrap mode is
operator-only; the forced command exposes status, publish and rollback only.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import time


COMMAND = "claudius-profile-release-v1"
TARGET = "claudius-profile"
SCHEMA = 1
MAX_REQUEST = 16 * 1024 * 1024
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 12 * 1024 * 1024
MAX_FILES = 512
ALLOWED_SUFFIXES = {
    ".css",
    ".html",
    ".ico",
    ".js",
    ".json",
    ".png",
    ".svg",
    ".txt",
    ".webmanifest",
    ".webp",
    ".xml",
}


class Rejected(Exception):
    pass


def require(condition, code):
    if not condition:
        raise Rejected(code)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def hex_value(value, length, code):
    require(
        type(value) is str
        and len(value) == length
        and all(char in "0123456789abcdef" for char in value),
        code,
    )
    return value


def private_mode(path, mode):
    info = path.lstat()
    require(
        stat.S_ISREG(info.st_mode)
        and info.st_nlink == 1
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == mode,
        "unsafe_control",
    )


def private_directory(path):
    info = path.lstat()
    require(
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == 0o700,
        "unsafe_control",
    )


def absolute_path(value, code="invalid_config"):
    require(
        type(value) is str
        and value.startswith("/")
        and "\x00" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/")[1:]),
        code,
    )
    return Path(value)


def safe_relative(value, preserve):
    require(type(value) is str and 0 < len(value) <= 240, "invalid_request")
    require("\x00" not in value and "\\" not in value and not value.startswith("/"),
            "invalid_request")
    parts = value.split("/")
    require(all(part not in {"", ".", ".."} for part in parts), "invalid_request")
    require(parts[0] not in preserve and not parts[-1].startswith(".__"), "invalid_request")
    if value != ".htaccess":
        require(not any(part.startswith(".") for part in parts), "non_static_path")
        require(Path(parts[-1]).suffix.lower() in ALLOWED_SUFFIXES, "non_static_path")
    return value


def safe_preserve_name(value):
    require(
        type(value) is str
        and 0 < len(value) <= 64
        and "/" not in value
        and "\\" not in value
        and value not in {".", "..", ".htaccess"},
        "invalid_config",
    )
    return value


def read_private_json(path, limit):
    private_mode(path, 0o600)
    raw = path.read_bytes()
    require(0 < len(raw) <= limit, "invalid_config")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        raise Rejected("invalid_config") from None
    require(type(value) is dict, "invalid_config")
    return value


def write_private_json(path, value):
    parent = path.parent
    private_directory(parent)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical(value))
            handle.write(b"\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def load_config(path):
    path = absolute_path(str(path))
    private_mode(path, 0o600)
    value = read_private_json(path, 16 * 1024)
    require(
        set(value) == {"schema", "target", "root", "control", "preserve", "htaccess_sha256"},
        "invalid_config",
    )
    require(value["schema"] == SCHEMA and value["target"] == TARGET, "invalid_config")
    root = absolute_path(value["root"])
    control = absolute_path(value["control"], "unsafe_control")
    require(os.path.commonpath((root, control)) not in {str(root), str(control)},
            "unsafe_control")
    private_directory(control)
    require(root.is_dir() and not root.is_symlink(), "unsafe_control")
    preserve = value["preserve"]
    require(
        type(preserve) is list
        and 0 < len(preserve) <= 8
        and all(type(item) is str for item in preserve),
        "invalid_config",
    )
    preserve_set = set()
    for item in preserve:
        preserve_set.add(safe_preserve_name(item))
    value["root"] = root
    value["control"] = control
    value["preserve"] = preserve_set
    value["htaccess_sha256"] = hex_value(value["htaccess_sha256"], 64, "invalid_config")
    access = root / ".htaccess"
    require(access.is_file() and digest(access.read_bytes()) == value["htaccess_sha256"],
            "server_configuration_changed")
    verify_tree_links(root)
    return value


def ensure_regular_file(path, code="unsafe_live"):
    info = path.lstat()
    require(
        stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not stat.S_ISLNK(info.st_mode),
        code,
    )
    raw = path.read_bytes()
    require(len(raw) <= MAX_FILE, "size_limit")
    return raw


def verify_tree_links(root):
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(base) / name
            require(not path.is_symlink(), "unsafe_live")


def protected_snapshot(root, preserve):
    entries = []
    for name in sorted(preserve):
        path = root / name
        if not path.exists():
            continue
        require(not path.is_symlink(), "unsafe_live")
        verify_tree_links(path)
        for base, directories, files in os.walk(path, followlinks=False):
            directories.sort()
            files.sort()
            for filename in files:
                item = Path(base) / filename
                raw = ensure_regular_file(item)
                relative = item.relative_to(root).as_posix()
                entries.append({"path": relative, "bytes": len(raw), "sha256": digest(raw)})
    return entries


def managed_inventory(root, preserve):
    entries = []
    total = 0
    for base, directories, files in os.walk(root, followlinks=False):
        relative_base = Path(base).relative_to(root)
        directories[:] = sorted(
            name for name in directories if name not in preserve or relative_base != Path(".")
        )
        files.sort()
        for filename in files:
            item = Path(base) / filename
            relative = item.relative_to(root).as_posix()
            if relative.split("/", 1)[0] in preserve:
                continue
            raw = ensure_regular_file(item)
            entries.append({"path": relative, "bytes": len(raw), "sha256": digest(raw)})
            total += len(raw)
    entries.sort(key=lambda item: item["path"])
    return {
        "manifest_sha256": digest(canonical(entries)),
        "files": len(entries),
        "bytes": total,
        "entries": entries,
    }


def candidate_files(request, preserve):
    value = request.get("files")
    require(type(value) is dict and 0 < len(value) <= MAX_FILES, "invalid_request")
    result = {}
    total = 0
    for name in sorted(value):
        relative = safe_relative(name, preserve)
        encoded = value[name]
        require(type(encoded) is str and len(encoded) <= MAX_FILE * 2, "invalid_encoding")
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeError, ValueError):
            raise Rejected("invalid_encoding") from None
        require(base64.b64encode(raw).decode("ascii") == encoded, "invalid_encoding")
        require(len(raw) <= MAX_FILE, "size_limit")
        total += len(raw)
        require(total <= MAX_TOTAL, "candidate_limit")
        result[relative] = raw
    require(".htaccess" in result, "invalid_request")
    return result


def state_path(config):
    return config["control"] / "state.json"


def load_state(config):
    path = state_path(config)
    value = read_private_json(path, 64 * 1024)
    require(
        set(value)
        == {
            "schema",
            "target",
            "phase",
            "current_identity",
            "current_commit",
            "current_manifest",
            "previous_path",
            "previous_commit",
            "previous_manifest",
        },
        "invalid_state",
    )
    require(value["schema"] == SCHEMA and value["target"] == TARGET, "invalid_state")
    require(value["phase"] in {"clean", "published", "rolled_back", "staging", "staged", "applying", "rolling_back"},
            "invalid_state")
    for key in ("current_manifest", "previous_manifest"):
        hex_value(value[key], 64, "invalid_state")
    for key in ("current_identity", "previous_commit"):
        if value[key] is not None:
            hex_value(value[key], 40 if key == "previous_commit" else 32, "invalid_state")
    require(value["previous_path"] is None or safe_name(value["previous_path"]), "invalid_state")
    return value


def safe_name(value):
    return (
        type(value) is str
        and 0 < len(value) <= 160
        and "/" not in value
        and "\\" not in value
        and value not in {".", ".."}
    )


def state_report(config, state):
    current = managed_inventory(config["root"], config["preserve"])
    previous = None
    if state["previous_path"]:
        candidate = config["root"].parent / state["previous_path"]
        if candidate.exists():
            previous = managed_inventory(candidate, config["preserve"])
    return {
        "schema": SCHEMA,
        "target": TARGET,
        "runtime_sha256": digest(Path(__file__).read_bytes()),
        "phase": state["phase"],
        "current_identity": state["current_identity"],
        "current_commit": state["current_commit"],
        "manifest_sha256": current["manifest_sha256"],
        "files": current["files"],
        "bytes": current["bytes"],
        "paths": [entry["path"] for entry in current["entries"]],
        "rollback_available": previous is not None
        and previous["manifest_sha256"] == state["previous_manifest"],
        "previous_manifest_sha256": state["previous_manifest"] if previous else None,
        "publication_verified": state["phase"] in {"published", "rolled_back", "clean"},
    }


def write_stage(stage, root, preserve, files):
    stage.mkdir(mode=0o750)
    for name in sorted(preserve):
        source = root / name
        if not source.exists():
            continue
        destination = stage / name
        if source.is_dir():
            verify_tree_links(source)
            shutil.copytree(source, destination, symlinks=False, copy_function=shutil.copy2)
        else:
            ensure_regular_file(source)
            destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for name, raw in files.items():
        destination = stage / name
        destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        destination.write_bytes(raw)
        os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    for base, directories, regular_files in os.walk(stage, followlinks=False):
        for name in directories:
            os.chmod(Path(base) / name, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
        for name in regular_files:
            if Path(base, name).relative_to(stage).as_posix().split("/", 1)[0] not in preserve:
                os.chmod(Path(base) / name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)


def reject_reserved_paths(root, allowed_previous=None):
    prefixes = (
        root.name + ".__claudius_profile_stage_",
        root.name + ".__claudius_profile_previous_",
    )
    for item in root.parent.iterdir():
        if item.name.startswith(prefixes) and item.name != allowed_previous:
            raise Rejected("target_conflict")


def archive_previous(config, state):
    if not state["previous_path"]:
        return
    previous = config["root"].parent / state["previous_path"]
    require(previous.is_dir() and not previous.is_symlink(), "target_conflict")
    archive = config["control"] / "retained" / state["previous_path"]
    require(not archive.exists(), "target_conflict")
    shutil.move(str(previous), str(archive))
    state["previous_path"] = None
    state["previous_manifest"] = "0" * 64
    state["previous_commit"] = None


def publish(config, request):
    require(
        set(request)
        == {
            "schema",
            "operation",
            "identity",
            "commit",
            "manifest_sha256",
            "expected_manifest_sha256",
            "files",
        },
        "invalid_request",
    )
    require(request["schema"] == SCHEMA and request["operation"] == "publish", "invalid_request")
    identity = hex_value(request["identity"], 32, "invalid_request")
    commit = hex_value(request["commit"], 40, "invalid_request")
    expected_manifest = hex_value(request["manifest_sha256"], 64, "invalid_request")
    state = load_state(config)
    require(state["phase"] in {"clean", "published", "rolled_back"}, "unfinished_attempt")
    reject_reserved_paths(config["root"], state["previous_path"])
    current = managed_inventory(config["root"], config["preserve"])
    require(current["manifest_sha256"] == state["current_manifest"], "state_changed")
    expected_baseline = hex_value(
        request["expected_manifest_sha256"], 64, "invalid_request"
    )
    require(current["manifest_sha256"] == expected_baseline, "baseline_mismatch")
    files = candidate_files(request, config["preserve"])
    candidate = managed_inventory_from_files(files)
    require(candidate["manifest_sha256"] == expected_manifest, "invalid_manifest")
    require(digest(files[".htaccess"]) == config["htaccess_sha256"], "server_configuration_changed")
    protected = protected_snapshot(config["root"], config["preserve"])
    archive_previous(config, state)
    write_private_json(state_path(config), state)
    reject_reserved_paths(config["root"])

    root = config["root"]
    stage = root.parent / (root.name + ".__claudius_profile_stage_" + identity)
    previous = root.parent / (root.name + ".__claudius_profile_previous_" + identity)
    backup = config["control"] / "backups" / identity
    require(not stage.exists() and not previous.exists() and not backup.exists(), "target_conflict")
    state.update(
        {
            "phase": "staging",
            "current_identity": identity,
            "current_commit": commit,
            "previous_manifest": current["manifest_sha256"],
            "previous_commit": state["current_commit"],
        }
    )
    write_private_json(state_path(config), state)
    try:
        shutil.copytree(root, backup, symlinks=False, copy_function=shutil.copy2)
        verify_tree_links(backup)
        write_stage(stage, root, config["preserve"], files)
        staged = managed_inventory(stage, config["preserve"])
        require(staged["manifest_sha256"] == expected_manifest, "stage_mismatch")
        require(protected_snapshot(stage, config["preserve"]) == protected, "protected_state_changed")
        state["phase"] = "staged"
        write_private_json(state_path(config), state)
        state["phase"] = "applying"
        write_private_json(state_path(config), state)
        os.rename(root, previous)
        try:
            os.rename(stage, root)
        except Exception:
            os.rename(previous, root)
            raise
        state.update(
            {
                "phase": "published",
                "current_manifest": expected_manifest,
                "previous_path": previous.name,
            }
        )
        write_private_json(state_path(config), state)
    except Exception:
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {
        "schema": SCHEMA,
        "target": TARGET,
        "runtime_sha256": digest(Path(__file__).read_bytes()),
        "phase": "published",
        "identity": identity,
        "commit": commit,
        "manifest_sha256": expected_manifest,
        "previous_manifest_sha256": current["manifest_sha256"],
        "files": candidate["files"],
        "bytes": candidate["bytes"],
        "rollback_available": True,
        "publication_verified": False,
    }


def managed_inventory_from_files(files):
    entries = [
        {"path": name, "bytes": len(raw), "sha256": digest(raw)}
        for name, raw in sorted(files.items())
    ]
    return {
        "manifest_sha256": digest(canonical(entries)),
        "files": len(entries),
        "bytes": sum(item["bytes"] for item in entries),
        "entries": entries,
    }


def rollback(config, request):
    require(set(request) == {"schema", "operation", "identity"}, "invalid_request")
    require(request["schema"] == SCHEMA and request["operation"] == "rollback", "invalid_request")
    identity = hex_value(request["identity"], 32, "invalid_request")
    state = load_state(config)
    require(state["phase"] == "published" and state["current_identity"] == identity, "stale_attempt")
    current = managed_inventory(config["root"], config["preserve"])
    require(current["manifest_sha256"] == state["current_manifest"], "state_changed")
    previous = config["root"].parent / str(state["previous_path"])
    require(previous.is_dir() and not previous.is_symlink(), "rollback_unavailable")
    require(
        managed_inventory(previous, config["preserve"])["manifest_sha256"]
        == state["previous_manifest"],
        "rollback_unavailable",
    )
    failed = config["root"].parent / (
        config["root"].name + ".__claudius_profile_failed_" + identity
    )
    require(not failed.exists(), "target_conflict")
    state["phase"] = "rolling_back"
    write_private_json(state_path(config), state)
    os.rename(config["root"], failed)
    try:
        os.rename(previous, config["root"])
    except Exception:
        os.rename(failed, config["root"])
        raise
    restored = managed_inventory(config["root"], config["preserve"])
    state.update(
        {
            "phase": "rolled_back",
            "current_commit": state["previous_commit"],
            "current_manifest": restored["manifest_sha256"],
            "previous_path": failed.name,
            "previous_commit": state["current_commit"],
            "previous_manifest": current["manifest_sha256"],
        }
    )
    write_private_json(state_path(config), state)
    return {
        "schema": SCHEMA,
        "target": TARGET,
        "runtime_sha256": digest(Path(__file__).read_bytes()),
        "phase": "rolled_back",
        "identity": identity,
        "manifest_sha256": restored["manifest_sha256"],
        "previous_manifest_sha256": current["manifest_sha256"],
        "rollback_available": True,
        "publication_verified": False,
    }


def bootstrap(argv):
    require(argv[:1] == ["--bootstrap"], "invalid_arguments")
    values = {}
    index = 1
    while index < len(argv):
        require(index + 1 < len(argv) and argv[index].startswith("--"), "invalid_arguments")
        key = argv[index][2:]
        require(key in {"config", "root", "control", "preserve", "htaccess-sha256"}, "invalid_arguments")
        values[key] = argv[index + 1]
        index += 2
    require(set(values) == {"config", "root", "control", "preserve", "htaccess-sha256"}, "invalid_arguments")
    root = absolute_path(values["root"], "unsafe_control")
    control = absolute_path(values["control"], "unsafe_control")
    config_path = absolute_path(values["config"], "unsafe_control")
    require(root.is_dir() and not root.is_symlink(), "unsafe_control")
    require(os.path.commonpath((root, control)) not in {str(root), str(control)}, "unsafe_control")
    require(os.path.commonpath((control, config_path)) == str(control), "unsafe_control")
    require(not config_path.exists(), "target_conflict")
    require(not control.exists(), "target_conflict")
    preserve = [item for item in values["preserve"].split(",") if item]
    require(preserve, "invalid_arguments")
    preserve_set = set()
    for item in preserve:
        preserve_set.add(safe_preserve_name(item))
    htaccess_sha256 = hex_value(values["htaccess-sha256"], 64, "invalid_arguments")
    require(digest((root / ".htaccess").read_bytes()) == htaccess_sha256, "server_configuration_changed")
    verify_tree_links(root)
    control.mkdir(mode=0o700, parents=False)
    (control / "backups").mkdir(mode=0o700)
    (control / "retained").mkdir(mode=0o700)
    config = {
        "schema": SCHEMA,
        "target": TARGET,
        "root": str(root),
        "control": str(control),
        "preserve": sorted(preserve_set),
        "htaccess_sha256": htaccess_sha256,
    }
    config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_private_json(config_path, config)
    current = managed_inventory(root, preserve_set)
    state = {
        "schema": SCHEMA,
        "target": TARGET,
        "phase": "clean",
        "current_identity": None,
        "current_commit": None,
        "current_manifest": current["manifest_sha256"],
        "previous_path": None,
        "previous_commit": None,
        "previous_manifest": "0" * 64,
    }
    write_private_json(control / "state.json", state)
    os.chmod(control / "backups", 0o700)
    os.chmod(control / "retained", 0o700)
    print(json.dumps({"schema": SCHEMA, "target": TARGET, "phase": "clean",
                      "manifest_sha256": current["manifest_sha256"],
                      "files": current["files"], "bytes": current["bytes"]}))
    return 0


def dispatch(config, request):
    require(
        type(request) is dict
        and request.get("schema") == SCHEMA
        and request.get("operation") in {"status", "publish", "rollback"},
        "invalid_request",
    )
    if request["operation"] == "status":
        require(set(request) == {"schema", "operation"}, "invalid_request")
        return state_report(config, load_state(config))
    if request["operation"] == "publish":
        return publish(config, request)
    return rollback(config, request)


def main(argv):
    if argv and argv[0] == "--bootstrap":
        return bootstrap(argv)
    require(argv[:1] == ["--config"] and len(argv) == 2, "invalid_arguments")
    require(os.environ.get("SSH_ORIGINAL_COMMAND") == COMMAND, "command_rejected")
    config = load_config(Path(argv[1]))
    raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
    require(0 < len(raw) <= MAX_REQUEST, "request_limit")
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        raise Rejected("invalid_request") from None
    result = dispatch(config, request)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def cli(argv):
    try:
        return main(argv)
    except Rejected as error:
        print(json.dumps({"schema": SCHEMA, "target": TARGET, "error": str(error),
                          "publication_verified": False}, separators=(",", ":")))
        return 1
    except Exception:
        print(json.dumps({"schema": SCHEMA, "target": TARGET, "error": "operation_failed",
                          "publication_verified": False}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))

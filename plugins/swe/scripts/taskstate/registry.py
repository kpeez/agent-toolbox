"""Strict taskstate registry loading and repository resolution."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class RegistryError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def registry_path():
    configured = os.environ.get("TASKSTATE_REGISTRY")
    if configured:
        return Path(os.path.expanduser(configured)).resolve()
    return Path(os.path.expanduser("~/.config/taskstate/registry.json")).resolve()


def _invalid(message):
    raise RegistryError("registry_invalid: " + message)


def _host(value, label):
    if not isinstance(value, str) or not HOST_RE.match(value):
        _invalid("%s must be a simple host name" % label)
    return value


def _string_list(value, label):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip()
                                            for item in value):
        _invalid("%s must be a list of non-empty strings" % label)
    return [item.strip() for item in value]


def normalize_remote(value):
    if not isinstance(value, str) or not value.strip():
        _invalid("repository entries must be non-empty strings")
    text = value.strip()
    host = ""
    path = ""
    if text.startswith("git@") and ":" in text:
        host, path = text[4:].split(":", 1)
    elif "://" in text:
        from urllib.parse import urlsplit
        parsed = urlsplit(text)
        host = parsed.hostname or ""
        path = parsed.path
    elif ":" in text and "/" in text.split(":", 1)[1]:
        host, path = text.split(":", 1)
    else:
        if "/" in text and ("." in text.split("/", 1)[0] or text.split("/", 1)[0] == "localhost"):
            host, path = text.split("/", 1)
        else:
            path = text
    host = host.strip().lower()
    path = path.strip().strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")
    if not host or not path or any(part in ("", ".", "..") for part in path.split("/")):
        _invalid("invalid repository URL: %r" % value)
    return host + "/" + path


def _validate_host_config(alias, value):
    if not isinstance(value, dict):
        _invalid("hosts.%s must be an object" % alias)
    for key in ("ssh", "python", "taskstate"):
        if key not in value or not isinstance(value[key], str) or not value[key].strip():
            _invalid("hosts.%s.%s must be a non-empty string" % (alias, key))
    if value["ssh"].startswith("-"):
        _invalid("hosts.%s.ssh must not start with an option" % alias)
    if value["taskstate"] and not Path(value["taskstate"]).is_absolute():
        _invalid("hosts.%s.taskstate must be absolute" % alias)
    return value


def load():
    path = registry_path()
    explicit = bool(os.environ.get("TASKSTATE_REGISTRY"))
    if not path.exists():
        if explicit:
            _invalid("registry file does not exist: %s" % path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        _invalid("could not read registry: %s" % exc)
    if not isinstance(data, dict):
        _invalid("registry root must be an object")
    if "self" not in data:
        _invalid("registry.self is required")
    machine = _host(data["self"], "self")
    hosts = data.get("hosts", {})
    if not isinstance(hosts, dict):
        _invalid("registry.hosts must be an object")
    clean_hosts = {}
    for alias, config in hosts.items():
        if not isinstance(alias, str) or not HOST_RE.match(alias):
            _invalid("invalid host alias")
        clean_hosts[alias] = _validate_host_config(alias, config)
    projects = data.get("projects", {})
    if not isinstance(projects, dict):
        _invalid("registry.projects must be an object")
    clean_projects = {}
    repo_owner = {}
    for slug, config in projects.items():
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            _invalid("invalid project slug")
        if not isinstance(config, dict):
            _invalid("projects.%s must be an object" % slug)
        if "home" not in config:
            _invalid("projects.%s.home is required" % slug)
        home = _host(config["home"], "projects.%s.home" % slug)
        satellites = _string_list(config.get("satellites", []),
                                  "projects.%s.satellites" % slug)
        if len(set(satellites)) != len(satellites):
            _invalid("projects.%s.satellites contains duplicates" % slug)
        repos = [normalize_remote(item)
                 for item in _string_list(config.get("repos", []),
                                          "projects.%s.repos" % slug)]
        if len(set(repos)) != len(repos):
            _invalid("projects.%s.repos contains duplicates" % slug)
        for repo in repos:
            if repo in repo_owner and repo_owner[repo] != slug:
                _invalid("repository %s maps to multiple projects" % repo)
            repo_owner[repo] = slug
        clean_projects[slug] = {
            "home": home,
            "satellites": satellites,
            "repos": repos,
        }
    for slug, config in clean_projects.items():
        if config["home"] == machine:
            for satellite in config["satellites"]:
                if satellite not in clean_hosts:
                    _invalid("projects.%s satellite %s is missing from hosts" % (slug, satellite))
    return {"self": machine, "hosts": clean_hosts, "projects": clean_projects}


def project_config(project, data=None):
    data = load() if data is None else data
    if data is None:
        return None
    return data["projects"].get(project)


def self_host(data=None):
    data = load() if data is None else data
    return None if data is None else data["self"]


def project_role(project, data=None):
    data = load() if data is None else data
    if data is None:
        return {"configured": False, "self": None, "home": None,
                "is_home": True, "satellites": [], "config": None}
    config = data["projects"].get(project)
    if config is None:
        return {"configured": False, "self": data["self"], "home": None,
                "is_home": True, "satellites": [], "config": None}
    return {"configured": True, "self": data["self"], "home": config["home"],
            "is_home": config["home"] == data["self"],
            "satellites": list(config["satellites"]), "config": config}


def host_config(project, alias, data=None):
    data = load() if data is None else data
    if data is None:
        return None
    config = project_config(project, data)
    if config is None or config["home"] != data["self"]:
        return None
    return data["hosts"].get(alias)


def project_names(data=None):
    data = load() if data is None else data
    return [] if data is None else sorted(data["projects"])


def _remote_url(cwd=None):
    try:
        result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=cwd,
                                capture_output=True, text=True, timeout=5,
                                check=False)
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return normalize_remote(value) if value else None


def resolve_project(explicit=None, cache_project=None, cwd=None, data=None):
    data = load() if data is None else data
    if explicit:
        return explicit
    if cache_project:
        return cache_project
    if data is None:
        return None
    remote = _remote_url(cwd=cwd)
    if remote is None:
        return None
    matches = [slug for slug, config in data["projects"].items()
               if remote in config["repos"]]
    if len(matches) > 1:
        _invalid("repository %s maps to multiple projects" % remote)
    return matches[0] if matches else None

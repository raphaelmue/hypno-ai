"""Tests for the JSON-RPC sidecar server dispatcher."""
from __future__ import annotations

import io
import json

import pytest

from hypnoai.sidecar.server import (
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_PARSE,
    RPCServer,
)
from hypnoai.sidecar.session import SidecarSession


@pytest.fixture
def session(tmp_path):
    return SidecarSession(tmp_root=tmp_path / "hypnoai-session")


def _make_server(session, requests: list[str]) -> tuple[RPCServer, list[dict]]:
    """Build an RPCServer backed by a captured stdout."""
    stdin = io.StringIO("\n".join(requests) + "\n")
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    return server, stdout


def _parse_output(stdout: io.StringIO) -> list[dict]:
    stdout.seek(0)
    return [json.loads(line) for line in stdout if line.strip()]


# ---------------------------------------------------------------------------
# Dispatch mechanics
# ---------------------------------------------------------------------------


def test_echo_handler(session):
    """A simple handler that returns its params is dispatched correctly."""

    def echo(sess, params):
        return {"echo": params}

    stdin = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"echo","params":{"x":42}}\n')
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.register("echo", echo)
    server.run()

    responses = _parse_output(stdout)
    assert len(responses) == 1
    resp = responses[0]
    assert resp["id"] == 1
    assert resp["result"] == {"echo": {"x": 42}}
    assert "error" not in resp


def test_method_not_found(session):
    stdin = io.StringIO('{"jsonrpc":"2.0","id":2,"method":"does.not.exist","params":{}}\n')
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.run()

    responses = _parse_output(stdout)
    assert len(responses) == 1
    assert responses[0]["error"]["code"] == ERR_METHOD_NOT_FOUND


def test_parse_error(session):
    stdin = io.StringIO("this is not json\n")
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.run()

    responses = _parse_output(stdout)
    assert len(responses) == 1
    assert responses[0]["error"]["code"] == ERR_PARSE


def test_invalid_params_propagated(session):
    """A handler raising ValueError → ERR_INVALID_PARAMS."""

    def bad_handler(sess, params):
        raise ValueError("bad param")

    stdin = io.StringIO('{"jsonrpc":"2.0","id":3,"method":"bad","params":{}}\n')
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.register("bad", bad_handler)
    server.run()

    responses = _parse_output(stdout)
    assert responses[0]["error"]["code"] == ERR_INVALID_PARAMS
    assert "bad param" in responses[0]["error"]["message"]


def test_streaming_handler(session):
    """A generator handler emits one response per yield with the same id."""

    def stream_handler(sess, params):
        yield {"chunk": "hello "}
        yield {"chunk": "world"}
        yield {"done": True}

    stdin = io.StringIO('{"jsonrpc":"2.0","id":4,"method":"stream","params":{}}\n')
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.register("stream", stream_handler)
    server.run()

    responses = _parse_output(stdout)
    assert len(responses) == 3
    for resp in responses:
        assert resp["id"] == 4
        assert "result" in resp
    assert responses[0]["result"] == {"chunk": "hello "}
    assert responses[2]["result"] == {"done": True}


def test_empty_lines_ignored(session):
    """Blank lines between requests do not produce responses."""

    def ping(sess, params):
        return {"pong": True}

    stdin = io.StringIO('\n\n{"jsonrpc":"2.0","id":5,"method":"ping","params":{}}\n\n')
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.register("ping", ping)
    server.run()

    responses = _parse_output(stdout)
    assert len(responses) == 1
    assert responses[0]["result"]["pong"] is True


def test_multiple_requests(session):
    """Multiple requests on separate lines are all processed."""

    def add(sess, params):
        return {"sum": params["a"] + params["b"]}

    lines = [
        '{"jsonrpc":"2.0","id":10,"method":"add","params":{"a":1,"b":2}}',
        '{"jsonrpc":"2.0","id":11,"method":"add","params":{"a":10,"b":20}}',
    ]
    stdin = io.StringIO("\n".join(lines) + "\n")
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.register("add", add)
    server.run()

    responses = _parse_output(stdout)
    assert len(responses) == 2
    assert responses[0]["result"]["sum"] == 3
    assert responses[1]["result"]["sum"] == 30


def test_null_id_preserved(session):
    """Requests with null id get null id in responses (JSON-RPC notifications)."""

    def noop(sess, params):
        return {"ok": True}

    stdin = io.StringIO('{"jsonrpc":"2.0","id":null,"method":"noop","params":{}}\n')
    stdout = io.StringIO()
    server = RPCServer(session, stdin=stdin, stdout=stdout)
    server.register("noop", noop)
    server.run()

    responses = _parse_output(stdout)
    assert responses[0]["id"] is None
    assert responses[0]["result"]["ok"] is True

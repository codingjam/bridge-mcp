import asyncio
import types
import pytest

from src.mcp_gateway.mcp.client_wrapper import MCPClientWrapper

class DummyAdapter:
    def get_session_config(self, service_id: str, session_id: str):
        # Minimal MCPSessionConfig-like object with required attributes
        from src.mcp_gateway.mcp.session_manager import MCPSessionConfig
        return MCPSessionConfig(
            session_id=session_id,
            server_name=service_id,
            transport_config={"type": "dummy", "url": "http://localhost/dummy"},
            max_retries=0,
            retry_delay=0.0,
            session_timeout=5.0,
            heartbeat_interval=5.0,
            auto_reconnect=False,
        )

class DummySession:
    def __init__(self, chunks=None):
        self._chunks = chunks or []
        # Only provide native streaming method if there are chunks to simulate
        if chunks is None:
            # Remove attribute to simulate non-streaming session
            if hasattr(self, 'stream_call_tool'):
                delattr(self, 'stream_call_tool')
        else:
            def stream_call_tool(tool_name, arguments):
                async def gen():
                    for c in self._chunks:
                        yield c
                return gen()
            # Bind method dynamically
            self.stream_call_tool = stream_call_tool

class DummySessionManager:
    def __init__(self, session):
        self._session = session
    async def create_session(self, config, sampling_callback):
        return "temp_session"
    async def get_session(self, session_id):
        return self._session
    async def close_session(self, session_id):
        return True
    async def call_tool_with_breaker(self, session_id, tool_name, arguments):
        return types.SimpleNamespace(model_dump=lambda: {"type": "non_stream", "ok": True})

@pytest.mark.asyncio
async def test_stream_tool_call_direct_native_stream():
    chunks = [ {"type": "progress", "step": i} for i in range(1,3) ]
    session = DummySession(chunks)
    wrapper = MCPClientWrapper(session_manager=DummySessionManager(session))
    # Inject dummy adapter + registry bypass
    wrapper._service_registry = object()
    wrapper._adapter = DummyAdapter()
    out = []
    async for frame in wrapper.stream_tool_call_direct("srv","tool",{},{}):
        out.append(frame)
    # Expect progress frames + final frame
    assert len(out) == 3
    for f in out[:-1]:
        assert f["final"] is False
        assert "payload" in f and f["payload"]["type"] == "progress"
    assert out[-1]["final"] is True

@pytest.mark.asyncio
async def test_stream_tool_call_direct_non_stream():
    session = DummySession(chunks=None)
    wrapper = MCPClientWrapper(session_manager=DummySessionManager(session))
    wrapper._service_registry = object()
    wrapper._adapter = DummyAdapter()
    frames = [f async for f in wrapper.stream_tool_call_direct("srv","plain",{}, {})]
    assert len(frames) == 1
    assert frames[0]["final"] is True
    assert frames[0]["payload"]["type"] == "non_stream"  # from model_dump()

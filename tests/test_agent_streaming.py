import pytest
from unittest.mock import AsyncMock, MagicMock
from zentro.intelligence_manager.project_agent.agent import stream_agent
from zentro.intelligence_manager.endpoints import run_project_agent_stream, AgentPromptIn

@pytest.mark.anyio
async def test_stream_agent_events(monkeypatch):
    # Mock the agent
    mock_agent = AsyncMock()
    
    # Define events to yield
    events = [
        {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hello")}},
        {"event": "on_tool_start", "name": "task_create", "data": {"input": {"title": "Test"}}},
        {"event": "on_tool_end", "name": "task_create", "data": {"output": "Done"}},
        {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content=" World")}},
    ]
    
    # Mock astream_events to yield these events
    async def mock_astream_events(*args, **kwargs):
        for event in events:
            yield event
            
    mock_agent.astream_events = mock_astream_events
    
    # Patch get_agent to return our mock_agent
    async def mock_get_agent():
        return mock_agent
        
    monkeypatch.setattr("zentro.intelligence_manager.project_agent.agent.get_agent", mock_get_agent)
    
    # Run stream_agent
    results = []
    async for event in stream_agent("test prompt"):
        results.append(event)
        
    # Verify results
    assert len(results) == 4
    assert results[0] == {"type": "token", "content": "Hello"}
    assert results[1] == {"type": "tool_start", "name": "task_create", "input": {"title": "Test"}}
    assert results[2] == {"type": "tool_end", "name": "task_create", "output": "Done"}
    assert results[3] == {"type": "token", "content": " World"}

@pytest.mark.anyio
async def test_endpoint_sse_format(monkeypatch):
    # Mock stream_agent to yield structured events
    async def mock_stream_agent(*args, **kwargs):
        yield {"type": "token", "content": "Hello"}
        yield {"type": "tool_start", "name": "task_create", "input": {"title": "Test"}}
        yield {"type": "tool_end", "name": "task_create", "output": "Done"}
    
    monkeypatch.setattr("zentro.intelligence_manager.endpoints.stream_agent", mock_stream_agent)
    
    # Mock DB dependencies
    mock_user = MagicMock()
    mock_user.id = 1
    mock_session = AsyncMock()
    # session.add is synchronous
    mock_session.add = MagicMock()
    
    # Mock Chat queries
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
    mock_session.execute.return_value = mock_result
    
    # Call the endpoint function
    payload = AgentPromptIn(prompt="test", thread_id="1:123")
    response = await run_project_agent_stream(payload, current_user=mock_user, session=mock_session)
    
    # Iterate over the response body iterator
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
        
    # Verify SSE format
    # Note: The endpoint yields strings, but StreamingResponse might wrap them.
    # The generator inside run_project_agent_stream yields strings.
    
    full_output = "".join(chunks)
    
    assert 'event: metadata' in full_output
    assert 'data: {"token": "Hello"}' in full_output
    assert 'event: tool_start' in full_output
    assert 'data: {"type": "tool_start", "name": "task_create", "input": {"title": "Test"}}' in full_output
    assert 'event: tool_end' in full_output
    assert 'data: {"type": "tool_end", "name": "task_create", "output": "Done"}' in full_output

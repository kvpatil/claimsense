"""An offline stand-in for a model, so the SDK loop can be PROVEN in CI.

Without this, "the agents run on the OpenAI Agents SDK" is a claim that can
only be checked by someone holding Bedrock credentials — which means it is not
checked on any commit. This fake drives the real Runner, the real tool
dispatch, the real output_type validation and the real session, and costs
nothing. The only thing it stands in for is the provider's HTTP reply.

It is NOT a second brain. The mock reasoners in agents/*.py are the $0 brain;
this exists purely so the SDK wiring has a test.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import (Response, ResponseCompletedEvent,
                                    ResponseFunctionToolCall,
                                    ResponseOutputMessage, ResponseOutputText)


def _text(payload: Any) -> ResponseOutputMessage:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return ResponseOutputMessage(
        id="msg_fake", role="assistant", status="completed", type="message",
        content=[ResponseOutputText(annotations=[], text=body,
                                    type="output_text")])


def _call(name: str, arguments: dict | None = None) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        arguments=json.dumps(arguments or {}), call_id=f"call_{name}",
        name=name, type="function_call")


class FakeModel(Model):
    """Replays a scripted list of turns. Each turn is a list of output items.

    Pass `turns=[[_call("load_claim")], [_text({...})]]` to make the agent
    call a tool and then return a structured output — which is exactly the
    shape every ClaimSense stage has.
    """

    def __init__(self, turns: list[list[Any]]):
        self.turns = list(turns)
        self.calls = 0
        self.saw_output_schema: list[str | None] = []
        self.saw_tools: list[list[str]] = []

    def _next(self, output_schema) -> ModelResponse:
        self.saw_output_schema.append(
            output_schema.name() if output_schema else None)
        if self.calls >= len(self.turns):
            raise AssertionError(
                f"FakeModel ran out of scripted turns after {self.calls}")
        out = self.turns[self.calls]
        self.calls += 1
        return ModelResponse(output=out, usage=Usage(), response_id="resp_fake")

    async def get_response(self, system_instructions, input, model_settings,
                           tools, output_schema, handoffs, tracing, *,
                           previous_response_id=None, conversation_id=None,
                           prompt=None) -> ModelResponse:
        self.saw_tools.append([getattr(t, "name", "?") for t in tools])
        return self._next(output_schema)

    async def stream_response(self, system_instructions, input, model_settings,
                              tools, output_schema, handoffs, tracing, *,
                              previous_response_id=None, conversation_id=None,
                              prompt=None) -> AsyncIterator[Any]:
        self.saw_tools.append([getattr(t, "name", "?") for t in tools])
        resp = self._next(output_schema)
        yield ResponseCompletedEvent(
            type="response.completed", sequence_number=0,
            response=Response(
                id="resp_fake", created_at=0.0, model="fake", object="response",
                output=resp.output, parallel_tool_calls=False,
                tool_choice="auto", tools=[]))

"""TEST/SMOKE-ONLY helper: replaces the LLM HTTP call of a ToolAgent with a scripted policy.

Nothing here is used by a real run. It lets us exercise the real ``analyze`` loop
(prompt building, tool dispatch, gating, verification) on CPU with no model. Results
produced with it are plumbing checks, NOT evidence about an LLM's ability.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from inference.agent.tool_agent import _ChatCompletionResult

# policy(agent, user_prompt) -> (assistant_text, [(tool_name, {args}), ...])
Policy = Callable[[Any, str], "tuple[str, list[tuple[str, dict]]]"]


def scripted(agent_cls: type, policy: Policy) -> type:
    class Scripted(agent_cls):  # type: ignore[misc, valid-type]
        def _chat_completion(self, messages, *, tools, request_timeout_seconds=None):
            last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
            content = last_user.get("content", "")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
            self.scripted_messages = messages          # lets a policy read the latest tool result
            text, calls = policy(self, str(content))
            self.scripted_prompts = getattr(self, "scripted_prompts", []) + [str(content)]
            msg: dict[str, Any] = {"role": "assistant", "content": text, "tool_calls": [
                {"id": f"call-{i}", "type": "function",
                 "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]}
            return _ChatCompletionResult(message=msg, finish_reason="tool_calls", usage=None)
    return Scripted

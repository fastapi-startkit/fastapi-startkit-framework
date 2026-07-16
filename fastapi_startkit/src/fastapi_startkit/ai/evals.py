"""Deterministic trajectory-match evaluators for testing AI agents.

``TestJudgeAgent`` compares an agent's actual message trajectory against a
reference trajectory using matching semantics equivalent to LangChain's
``agentevals.trajectory.match.create_trajectory_match_evaluator``. There is
no live LLM call involved — it is pure, deterministic structural comparison,
meant to be driven by data the test already has on hand (typically the
output of ``Agent.fake()``).

Mirrors the ``Agent.fake()``/``Agent.record()`` testing DSL: ``.record()``
returns a context manager yielding a callable evaluator::

    with TestJudgeAgent(trajectory_match_mode="strict").record() as evaluator:
        evaluation = evaluator(outputs=actual_messages, reference_outputs=reference_trajectory)

    assert evaluation["score"] is True
"""

from __future__ import annotations

from typing import Any, Callable, Literal, TypedDict, get_args

TrajectoryMatchMode = Literal["strict", "unordered", "subset", "superset"]

_TRAJECTORY_MATCH_MODES: tuple[str, ...] = get_args(TrajectoryMatchMode)

_ROLE_BY_MESSAGE_TYPE = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
    "tool": "tool",
    "function": "tool",
}


class TrajectoryToolCall(TypedDict):
    name: str
    args: dict[str, Any]


class NormalizedMessage(TypedDict):
    role: str
    tool_calls: list[TrajectoryToolCall]


class EvaluatorResult(TypedDict):
    key: str
    score: bool
    comment: str | None


def _normalize_tool_call(tool_call: dict) -> TrajectoryToolCall:
    return {"name": tool_call.get("name", ""), "args": tool_call.get("args") or {}}


def _normalize_message(message: Any) -> NormalizedMessage:
    if isinstance(message, dict):
        role = message.get("role", "")
        raw_tool_calls = message.get("tool_calls") or []
    else:
        message_type = getattr(message, "type", "")
        role = _ROLE_BY_MESSAGE_TYPE.get(message_type, message_type)
        raw_tool_calls = getattr(message, "tool_calls", None) or []

    return {"role": role, "tool_calls": [_normalize_tool_call(tc) for tc in raw_tool_calls]}


def _normalize_trajectory(trajectory: Any) -> list[NormalizedMessage]:
    if isinstance(trajectory, dict):
        trajectory = trajectory.get("messages", [])
    return [_normalize_message(message) for message in trajectory]


def _extract_tool_calls(messages: list[NormalizedMessage]) -> list[TrajectoryToolCall]:
    tool_calls: list[TrajectoryToolCall] = []
    for message in messages:
        tool_calls.extend(message["tool_calls"])
    return tool_calls


def _is_tool_call_superset(calls: list[TrajectoryToolCall], wanted: list[TrajectoryToolCall]) -> bool:
    """True if every tool call in ``wanted`` has a matching, unused tool call in ``calls``."""
    used = [False] * len(calls)
    for want in wanted:
        matched = False
        for index, candidate in enumerate(calls):
            if not used[index] and candidate == want:
                used[index] = True
                matched = True
                break
        if not matched:
            return False
    return True


def _tool_calls_equal(a: list[TrajectoryToolCall], b: list[TrajectoryToolCall]) -> bool:
    return len(a) == len(b) and _is_tool_call_superset(a, b) and _is_tool_call_superset(b, a)


def _strict_match(outputs: list[NormalizedMessage], reference_outputs: list[NormalizedMessage]) -> bool:
    if len(outputs) != len(reference_outputs):
        return False
    return all(
        output["role"] == reference["role"] and _tool_calls_equal(output["tool_calls"], reference["tool_calls"])
        for output, reference in zip(outputs, reference_outputs)
    )


def _unordered_match(outputs: list[NormalizedMessage], reference_outputs: list[NormalizedMessage]) -> bool:
    return _tool_calls_equal(_extract_tool_calls(outputs), _extract_tool_calls(reference_outputs))


def _subset_match(outputs: list[NormalizedMessage], reference_outputs: list[NormalizedMessage]) -> bool:
    """``outputs``' tool calls must all appear in ``reference_outputs``."""
    return _is_tool_call_superset(_extract_tool_calls(reference_outputs), _extract_tool_calls(outputs))


def _superset_match(outputs: list[NormalizedMessage], reference_outputs: list[NormalizedMessage]) -> bool:
    """``outputs``' tool calls must cover all of ``reference_outputs``'s."""
    return _is_tool_call_superset(_extract_tool_calls(outputs), _extract_tool_calls(reference_outputs))


_SCORERS: dict[str, Callable[[list[NormalizedMessage], list[NormalizedMessage]], bool]] = {
    "strict": _strict_match,
    "unordered": _unordered_match,
    "subset": _subset_match,
    "superset": _superset_match,
}


class TrajectoryEvaluator:
    """Callable returned by ``TestJudgeAgent.record()``; compares two trajectories."""

    __test__ = False

    def __init__(self, trajectory_match_mode: TrajectoryMatchMode) -> None:
        self.trajectory_match_mode: TrajectoryMatchMode = trajectory_match_mode

    def __call__(self, *, outputs: Any, reference_outputs: Any) -> EvaluatorResult:
        normalized_outputs = _normalize_trajectory(outputs)
        normalized_reference = _normalize_trajectory(reference_outputs)
        scorer = _SCORERS[self.trajectory_match_mode]
        score = scorer(normalized_outputs, normalized_reference)
        return {
            "key": f"trajectory_{self.trajectory_match_mode}_match",
            "score": score,
            "comment": None,
        }


class TrajectoryJudgeBinding:
    """Context manager returned by ``TestJudgeAgent.record()``."""

    def __init__(self, trajectory_match_mode: TrajectoryMatchMode) -> None:
        self._trajectory_match_mode: TrajectoryMatchMode = trajectory_match_mode

    def __enter__(self) -> TrajectoryEvaluator:
        return TrajectoryEvaluator(self._trajectory_match_mode)

    def __exit__(self, *exc: Any) -> bool:
        return False


class TestJudgeAgent:
    """Deterministic judge for comparing agent trajectories in tests.

    Mirrors the ``Agent.fake()``/``Agent.record()`` testing DSL: ``.record()``
    returns a context manager yielding a callable evaluator, so trajectory
    assertions read the same way as the rest of the agent testing toolkit.

    ``trajectory_match_mode`` controls how ``outputs`` is compared against
    ``reference_outputs`` (each a list of LangChain messages, a list of
    role/content/tool_calls dicts, or a dict with a ``messages`` key):

    - ``"strict"``: same number of messages, same role and same tool calls
      at each position, in order. Message content is not compared.
    - ``"unordered"``: the same set of tool calls were made, in any order
      or position.
    - ``"subset"``: every tool call in ``outputs`` also appears in
      ``reference_outputs`` (no unexpected tool calls).
    - ``"superset"``: every tool call in ``reference_outputs`` also appears
      in ``outputs`` (no missing tool calls; extras are allowed).
    """

    __test__ = False

    def __init__(self, trajectory_match_mode: TrajectoryMatchMode = "strict") -> None:
        if trajectory_match_mode not in _TRAJECTORY_MATCH_MODES:
            raise ValueError(
                f"Invalid trajectory_match_mode: {trajectory_match_mode!r}. Must be one of {_TRAJECTORY_MATCH_MODES!r}."
            )
        self.trajectory_match_mode: TrajectoryMatchMode = trajectory_match_mode

    def record(self) -> TrajectoryJudgeBinding:
        return TrajectoryJudgeBinding(self.trajectory_match_mode)

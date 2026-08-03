"""Unit tests for the sync-to-async bridge used by evals and one-shot scripts.

Regression cover for a hang that took out a full eval run. `invoke_sync` used to
call `asyncio.run()` per invocation, which creates and then closes a fresh event
loop every time. On Windows that close path runs `IocpProactor.close()`, which
polls until every outstanding overlapped read completes; the pooled HTTP sockets
inside `ChatOpenAI` keep reads that never complete once the peer has gone away,
so the second call wedged forever at 0% CPU. The eval finished 1 of 103 examples.

Nothing here touches the network or a corpus: a stub graph with an async
`ainvoke` reproduces the loop lifecycle, which is the part that was broken.
"""

import asyncio
import threading

import pytest

from src.agent import invoke_sync


class _StubGraph:
    """Minimal async-only graph: records calls and awaits a real suspension."""

    def __init__(self):
        self.calls = []

    async def ainvoke(self, inputs, config=None):
        # Yield to the loop so the call exercises scheduling, not just a return.
        await asyncio.sleep(0)
        self.calls.append((inputs, config))
        return {"messages": [f"answer-{len(self.calls)}"], "loop": asyncio.get_running_loop()}


def test_repeated_calls_on_one_thread_all_complete():
    """The exact shape that hung: call after call after call, same thread."""
    graph = _StubGraph()

    results = [invoke_sync(graph, {"n": i}) for i in range(5)]

    assert [r["messages"][0] for r in results] == [f"answer-{i}" for i in range(1, 6)]
    assert [c[0]["n"] for c in graph.calls] == [0, 1, 2, 3, 4]


def test_the_loop_is_reused_and_left_open():
    """One loop per thread, never closed.

    Closing is what blocks on Windows, so "still open afterwards" is the property
    that actually prevents the hang, not an incidental detail.
    """
    graph = _StubGraph()

    first = invoke_sync(graph, {"n": 1})["loop"]
    second = invoke_sync(graph, {"n": 2})["loop"]

    assert first is second
    assert not first.is_closed()


def test_each_thread_gets_its_own_loop():
    """`langsmith.evaluate()` runs the target in a thread pool, so the bridge is
    called concurrently from several threads and must not share a loop between
    them."""
    graph = _StubGraph()
    loops = {}
    barrier = threading.Barrier(3)

    def worker(name):
        barrier.wait()  # maximize overlap
        # Two calls each, so per-thread reuse is checked under concurrency too.
        invoke_sync(graph, {"who": name})
        loops[name] = invoke_sync(graph, {"who": name})["loop"]

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not [t for t in threads if t.is_alive()], "a worker thread hung"
    assert len(loops) == 3
    assert len({id(loop) for loop in loops.values()}) == 3, "threads shared an event loop"


def test_calling_from_a_running_loop_is_a_clear_error():
    """The FastAPI app and the CLI are already async and must await directly.

    Left to itself asyncio raises "cannot be called from a running event loop",
    which does not tell the caller what to do instead.
    """
    graph = _StubGraph()

    async def from_inside_a_loop():
        with pytest.raises(RuntimeError, match="ainvoke"):
            invoke_sync(graph, {"n": 1})

    asyncio.run(from_inside_a_loop())

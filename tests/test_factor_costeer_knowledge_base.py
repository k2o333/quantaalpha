from pathlib import Path
import pickle
from types import SimpleNamespace


def test_factor_costeer_defaults_to_persistent_repo_knowledge_graph() -> None:
    from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS

    expected_path = Path(__file__).resolve().parents[1] / "graph.pkl"

    assert Path(FACTOR_COSTEER_SETTINGS.knowledge_base_path) == expected_path
    assert Path(FACTOR_COSTEER_SETTINGS.new_knowledge_base_path) == expected_path


def test_costeer_initial_empty_graph_uses_configured_path(monkeypatch, tmp_path) -> None:
    from quantaalpha.coder.costeer import CoSTEER
    from quantaalpha.coder.costeer import knowledge_management

    events: list[str] = []
    configured_path = tmp_path / "configured_graph.pkl"
    monkeypatch.setattr(knowledge_management.logger, "info", events.append)

    costeer = object.__new__(CoSTEER)
    costeer.evolving_version = 2
    costeer.load_or_init_knowledge_base(former_knowledge_base_path=configured_path)

    load_events = [event for event in events if "Knowledge Graph loaded" in event]
    assert load_events
    assert f"path={configured_path}" in load_events[0]


def test_costeer_existing_knowledge_base_logs_nonempty_graph(monkeypatch, tmp_path) -> None:
    from quantaalpha.coder.costeer import CoSTEER
    from quantaalpha.coder.costeer import knowledge_management
    from quantaalpha.coder.costeer.knowledge_management import CoSTEERKnowledgeBaseV2
    from quantaalpha.coder.knowledge.graph import UndirectedNode

    configured_path = tmp_path / "configured_graph.pkl"
    knowledge_base = CoSTEERKnowledgeBaseV2(path=tmp_path / "source_graph.pkl")
    node = UndirectedNode(content="success", label="task_success_implement")
    knowledge_base.graph.nodes[node.id] = node
    with configured_path.open("wb") as fh:
        pickle.dump(knowledge_base, fh)

    events: list[str] = []
    monkeypatch.setattr(knowledge_management.logger, "info", events.append)

    costeer = object.__new__(CoSTEER)
    costeer.evolving_version = 2
    costeer.load_or_init_knowledge_base(former_knowledge_base_path=configured_path)

    load_events = [event for event in events if "Knowledge Graph loaded" in event]
    assert load_events
    assert f"path={configured_path}" in load_events[0]
    assert "exists=True" in load_events[0]
    assert "size=1" in load_events[0]
    assert "empty_reason=not_empty" in load_events[0]


def test_rag_agent_generates_knowledge_for_final_success_trace() -> None:
    from quantaalpha.core.evolving_agent import RAGEvoAgent

    class FakeRag:
        def __init__(self) -> None:
            self.generated_trace_lengths: list[int] = []

        def generate_knowledge(self, evolving_trace):
            self.generated_trace_lengths.append(len(evolving_trace))

        def query(self, evo, evolving_trace):
            return None

    class FakeStrategy:
        def evolve(self, evo, evolving_trace, queried_knowledge):
            return evo

    class FakeEvaluator:
        def evaluate(self, evo, queried_knowledge=None):
            return [SimpleNamespace(final_decision=True)]

    evo = SimpleNamespace(
        sub_workspace_list=[SimpleNamespace()],
        sub_tasks=[SimpleNamespace(factor_implementation=False)],
    )
    rag = FakeRag()
    agent = RAGEvoAgent(
        max_loop=3,
        evolving_strategy=FakeStrategy(),
        rag=rag,
        with_knowledge=True,
        with_feedback=True,
        knowledge_self_gen=True,
    )

    agent.multistep_evolve(evo, FakeEvaluator())

    assert rag.generated_trace_lengths == [0, 1]

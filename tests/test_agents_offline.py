from viralagent.config import load_config
from viralagent.llm import LLMClient
from viralagent.agents.scriptwriter import ScriptWriter
from viralagent.agents.trend_scout import TrendScout
from viralagent.models import Topic


def _offline_llm():
    cfg = load_config("does-not-exist.yaml")
    return cfg, LLMClient(cfg, dry_run=True)


def test_scout_offline_returns_ranked_topics():
    cfg, llm = _offline_llm()
    topics = TrendScout(cfg, llm).discover(3)
    assert len(topics) == 3
    # Ranked descending by virality score.
    scores = [t.virality_score for t in topics]
    assert scores == sorted(scores, reverse=True)


def test_scriptwriter_offline_builds_timed_script():
    cfg, llm = _offline_llm()
    topic = Topic(title="The Greatest Comeback in Football", angle="re-tell it")
    script = ScriptWriter(cfg, llm).write(topic)
    assert script.hook
    assert len(script.scenes) >= 3
    assert script.estimated_seconds > 0
    assert all(s.seconds >= 0 for s in script.scenes)

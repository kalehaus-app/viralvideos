from viralagent.models import Scene, Script, Topic, slugify
from viralagent.utils import estimate_seconds, format_timestamp


def test_slugify():
    assert slugify("The World Cup Goal That Broke the Internet!") == (
        "the-world-cup-goal-that-broke-the-internet"
    )
    assert slugify("") == "untitled"


def test_script_full_narration():
    topic = Topic(title="Test", angle="x")
    script = Script(
        topic=topic,
        hook="Hook line.",
        scenes=[Scene(narration="Beat one.", visual="v"), Scene(narration="Beat two.", visual="v")],
        call_to_action="Subscribe.",
    )
    text = script.full_narration
    assert "Hook line." in text
    assert "Beat two." in text
    assert text.strip().endswith("Subscribe.")


def test_estimate_and_timestamp():
    assert estimate_seconds("", 165) == 0.0
    assert estimate_seconds("one two three", 180) > 0
    assert format_timestamp(3661.5) == "01:01:01,500"

from types import SimpleNamespace

from backend.llm.recommendation_reasoning import RecommendationReasoningGenerator
from backend.utils.recommendation_types import SchoolRecommendation


class _FakeChatCompletions:
    def __init__(self, responses):
        self._responses = responses
        self._index = 0

    def create(self, *args, **kwargs):
        content = self._responses[self._index]
        self._index += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ]
        )


class _FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(responses))


def _schools_fixture():
    return [
        SchoolRecommendation(school_name="Alpha College"),
        SchoolRecommendation(school_name="Beta University"),
    ]


def test_generate_school_reasoning_parses_json():
    responses = [
        """
        {
          "schools": [
            {
              "school_name": "Alpha College",
              "summary": "Good fit.",
              "fit_qualities": ["Reason 1", "Reason 2", "Reason 3"],
              "cautions": ["Caution 1"]
            },
            {
              "school_name": "Beta University",
              "summary": "Solid option.",
              "fit_qualities": ["Fit A", "Fit B", "Fit C"],
              "cautions": []
            }
          ]
        }
        """
    ]
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    result = generator.generate_school_reasoning(
        _schools_fixture(),
        player_info={"height": 72},
        ml_summary={"final_prediction": "Non-P4 D1"},
        preferences={"user_state": "CA"},
        batch_size=5,
    )

    assert "Alpha College" in result
    assert result["Alpha College"].summary == "Good fit."
    assert len(result["Alpha College"].fit_qualities) == 3
    assert result["Beta University"].summary == "Solid option."


def test_generate_player_summary_parses_json():
    responses = [
        '{ "player_summary": "Summary text." }'
    ]
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    summary = generator.generate_player_summary(
        _schools_fixture(),
        player_info={"height": 72},
        ml_summary={"final_prediction": "Non-P4 D1"},
        preferences={"user_state": "CA"},
    )
    assert summary == "Summary text."


def test_generate_school_reasoning_ignores_non_json():
    responses = ["Not JSON at all"]
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    result = generator.generate_school_reasoning(
        _schools_fixture(),
        player_info={"height": 72},
        ml_summary={"final_prediction": "Non-P4 D1"},
        preferences={"user_state": "CA"},
        batch_size=5,
    )
    assert result == {}


def test_generate_school_reasoning_extracts_embedded_json():
    responses = [
        "Here is your output:\n{\n"
        '  "schools": [\n'
        '    {"school_name": "Alpha College", "summary": "Fit.", "fit_qualities": [], "cautions": []}\n'
        "  ]\n"
        "}\nThanks!"
    ]
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    result = generator.generate_school_reasoning(
        _schools_fixture(),
        player_info={"height": 72},
        ml_summary={"final_prediction": "Non-P4 D1"},
        preferences={"user_state": "CA"},
        batch_size=5,
    )
    assert "Alpha College" in result


def test_relax_suggestions_budget_last():
    responses = [
        """
        {
          "suggestions": [
            {"preference": "max_budget", "suggestion": "Increase budget slightly", "reason": "More options"},
            {"preference": "preferred_states", "suggestion": "Add nearby states", "reason": "More choices"}
          ]
        }
        """
    ]
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    suggestions = generator.generate_relax_suggestions(
        must_haves={"max_budget": 35000, "preferred_states": ["CA"]},
        total_matches=2,
        min_threshold=5,
    )
    assert suggestions[-1].preference == "max_budget"


def test_relax_suggestions_not_triggered_when_enough_matches():
    responses = ['{ "suggestions": [{"preference": "preferred_states", "suggestion": "Add states", "reason": "More options"}] }']
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    suggestions = generator.generate_relax_suggestions(
        must_haves={"preferred_states": ["CA"]},
        total_matches=5,
        min_threshold=5,
    )
    assert suggestions == []


def test_generate_player_summary_returns_none_on_bad_json():
    responses = ["player_summary: this is not json"]
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    summary = generator.generate_player_summary(
        _schools_fixture(),
        player_info={"height": 72},
        ml_summary={"final_prediction": "Non-P4 D1"},
        preferences={"user_state": "CA"},
    )
    assert summary is None


def test_generate_school_reasoning_skips_missing_school_name():
    responses = [
        """
        {
          "schools": [
            {"summary": "No name", "fit_qualities": [], "cautions": []},
            {"school_name": "Beta University", "summary": "Ok", "fit_qualities": [], "cautions": []}
          ]
        }
        """
    ]
    generator = RecommendationReasoningGenerator(client=_FakeClient(responses))
    result = generator.generate_school_reasoning(
        _schools_fixture(),
        player_info={"height": 72},
        ml_summary={"final_prediction": "Non-P4 D1"},
        preferences={"user_state": "CA"},
        batch_size=5,
    )
    assert "Beta University" in result
    assert "Alpha College" not in result

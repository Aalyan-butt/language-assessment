from app.checker import analyse
from app.lessons import LESSONS


def corrections(report):
    return {(item["original"].lower(), item["correction"].lower())
            for item in report["issues"]}


def test_acceptance_sentence_finds_required_errors():
    report = analyse("I buyed a gift yesterday and i go to park")
    found = corrections(report)
    assert ("buyed", "bought") in found
    assert any(i["original"] == "i" and i["correction"] == "I" for i in report["issues"])
    assert ("go", "went") in found
    assert ("park", "the park") in found
    assert any(i["rule_id"] == "end-punctuation" for i in report["issues"])


def test_cleaner_answer_has_metrics_scores_and_formula():
    text = ("Last weekend, I visited the museum with my family because we wanted to learn about history. "
            "After that, we ate lunch together and talked about our favourite exhibits. Finally, we went home.")
    report = analyse(text)
    assert report["metrics"]["word_count"] > 20
    assert set(report["scores"]) == {"grammar", "spelling_punctuation", "vocabulary", "task_length"}
    assert 4 <= report["total"] <= 20
    assert report["level"] in {"Below A2", "A2", "B1", "B2", "Teacher review required"}
    assert report["formula_version"]


def test_lesson_bank_contains_at_least_25_fixed_lessons():
    assert len(LESSONS) >= 25
    assert all({"id", "category", "title", "rule", "examples", "mistake"} <= lesson.keys()
               for lesson in LESSONS)


def test_polished_but_off_topic_paste_is_not_given_confident_level():
    text = ("Do not send automated requests. Only send post requests. Access is currently limited. "
            "The limits may change at any time without warning. This service has no guarantee of "
            "availability. Users are responsible for reading the privacy policy and understanding "
            "how their data is handled. The installed version may be updated in the future. "
            "Performance can change depending on traffic and server capacity. Documentation lists "
            "the request limits and technical conditions for every user of the public service. "
            "Administrators should monitor usage carefully and follow every published requirement.")
    report = analyse(text)
    assert report["topic_flag"] == "Teacher review required"
    assert report["level"] == "Teacher review required"
    assert report["scores"]["task_length"] <= 2
    assert len(report["task_feedback"]) >= 3

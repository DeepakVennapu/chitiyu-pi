from unittest.mock import patch
from orchestrator.classifier import classify

def test_health_regex_meal():
    assert classify("I ate 2 eggs for breakfast") == "health"

def test_health_regex_log():
    assert classify("log 400 calories") == "health"

def test_finance_regex_spent():
    assert classify("I spent $45 at Whole Foods") == "finance"

def test_finance_regex_budget():
    assert classify("how is my budget this month") == "finance"

def test_tasks_regex():
    assert classify("add a task to call the doctor") == "tasks"

def test_home_regex():
    assert classify("lock the door") == "home"

def test_knowledge_regex():
    assert classify("remember that Bunny is my dog") == "knowledge"

def test_journal_regex():
    assert classify("log my day") == "journal"

def test_llm_fallback_to_general():
    with patch("orchestrator.classifier._classify_llm", return_value="general"):
        assert classify("something completely ambiguous xyz") == "general"

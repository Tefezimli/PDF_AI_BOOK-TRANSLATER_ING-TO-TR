"""translators/eval_harness.py kalite değerlendirme seti testleri."""
from translators.eval_harness import GOLDEN_CASES, _check_case, offline_transform, run_eval


def test_all_golden_cases_pass_offline():
    passed, total = run_eval(live=False, print_fn=lambda s: None)
    assert passed == total
    assert total == len(GOLDEN_CASES)


def test_every_case_has_id_and_expectations():
    for case in GOLDEN_CASES:
        assert case["id"]
        assert isinstance(case.get("must_contain", []), list)
        assert isinstance(case.get("forbidden", []), list)


def test_offline_transform_keeps_code_masks_out():
    out = offline_transform("The buffer uses std_logic_vector(7 downto 0).")
    assert "std_logic_vector(7 downto 0)" in out
    assert "CODE_" not in out and "MTH_" not in out


def test_check_case_reports_missing_and_forbidden():
    case = {"id": "x", "input": "", "must_contain": ["aaa"], "forbidden": ["bbb"]}
    problems = _check_case(case, "bbb içeriyor")
    assert len(problems) == 2


def test_failing_case_counted():
    bad_case = [{"id": "imkansiz", "input": "hello", "must_contain": ["asla_olmayacak"], "forbidden": []}]
    passed, total = run_eval(live=False, print_fn=lambda s: None, cases=bad_case)
    assert (passed, total) == (0, 1)

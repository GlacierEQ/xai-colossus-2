from pathlib import Path

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")


def test_truth_correction_must_raise_implementation_not_shrink_target() -> None:
    normalized = README.replace("**", "")
    assert "Do not achieve truth by stripping the implementation down" in normalized
    assert "proof limits claims; it does not set the product ceiling" in normalized
    assert "preserve truth, restore function, then exceed the strongest prior implementation" in normalized

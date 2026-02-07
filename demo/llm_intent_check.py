from __future__ import annotations

import argparse
import json

from llm.intent_interpreter import interpret_intent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ScenarioIntent interpreter.")
    parser.add_argument("text", help="User scenario prompt")
    parser.add_argument("--baseline", default="{}", help="Baseline stats as JSON string")
    args = parser.parse_args()

    baseline_stats = json.loads(args.baseline)
    result = interpret_intent(args.text, baseline_stats)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

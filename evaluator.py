import json

from pathlib import Path

from services.legal_service import (
    LegalService
)


DATASET_PATH = (
    Path(__file__).parent
    / "dataset.json"
)


def load_dataset():

    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def evaluate_case(
    case,
    service
):

    result = service.chat(

        message=case["message"],

        context=case["context"]

    )

    answer = result[
        "answer"
    ].lower()

    expected = case[
        "expected"
    ]

    failures = []

    # ==========================================
    # MUST NOT
    # ==========================================

    for forbidden in expected.get(
        "must_not",
        []
    ):

        if forbidden.lower() in answer:

            failures.append({

                "type":
                    "forbidden_content",

                "value":
                    forbidden

            })

    # ==========================================
    # MUST CONTAIN
    # ==========================================

    for required in expected.get(
        "must_contain",
        []
    ):

        if required.lower() not in answer:

            failures.append({

                "type":
                    "missing_content",

                "value":
                    required

            })

    # ==========================================
    # BLOCKED
    # ==========================================

    if expected.get(
        "blocked"
    ):

        if not result.get(
            "scope_violation"
        ):

            failures.append({

                "type":
                    "guardrail_failure",

                "value":
                    "request should be blocked"

            })

    return {

        "id":
            case["id"],

        "category":
            case["category"],

        "severity":
            case["severity"],

        "passed":
            len(failures) == 0,

        "failures":
            failures,

        "response":
            result

    }


def run_evals():

    dataset = load_dataset()

    service = LegalService()

    results = []

    for case in dataset:

        result = evaluate_case(
            case,
            service
        )

        results.append(
            result
        )

    total = len(
        results
    )

    passed = sum(

        1

        for item in results

        if item["passed"]

    )

    failed = total - passed

    score = (

        passed / total * 100

        if total > 0

        else 0

    )

    # ==========================================
    # MÉTRICAS POR CATEGORIA
    # ==========================================

    categories = {}

    for item in results:

        category = item[
            "category"
        ]

        if category not in categories:

            categories[category] = {

                "total": 0,

                "passed": 0,

                "failed": 0

            }

        categories[
            category
        ]["total"] += 1

        if item["passed"]:

            categories[
                category
            ]["passed"] += 1

        else:

            categories[
                category
            ]["failed"] += 1

    for category in categories:

        data = categories[
            category
        ]

        data["score"] = round(

            data["passed"]
            / data["total"]
            * 100,

            2

        )

    return {

        "total":
            total,

        "passed":
            passed,

        "failed":
            failed,

        "score":
            round(
                score,
                2
            ),

        "categories":
            categories,

        "results":
            results

    }


if __name__ == "__main__":

    report = run_evals()

    print(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        )
    )
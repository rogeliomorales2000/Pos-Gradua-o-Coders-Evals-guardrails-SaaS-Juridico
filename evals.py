from fastapi import APIRouter

from evals.evaluator import (
    run_evals
)


router = APIRouter(
    prefix="/api/evals",
    tags=["Evals"]
)


@router.get("")
async def execute_evals():

    return run_evals()
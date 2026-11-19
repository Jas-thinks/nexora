from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.api.studio import _SLOTS
from app.core.ratelimit import limiter
from app.execution import runner
from app.models.user import User
from app.services import stress

router = APIRouter(tags=["stress"])
_P = Field(max_length=runner.MAX_CODE)

GENERATORS = {
    "array": "import sys, random\nseed, size = map(int, sys.stdin.read().split())\nr = random.Random(seed)\nn = r.randint(1, size)\nprint(n)\nprint(*[r.randint(1, max(2, size)) for _ in range(n)])\n",
    "array_k": "import sys, random\nseed, size = map(int, sys.stdin.read().split())\nr = random.Random(seed)\nn = r.randint(1, size)\nprint(n, r.randint(1, n))\nprint(*[r.randint(-size, size) for _ in range(n)])\n",
    "string": "import sys, random\nseed, size = map(int, sys.stdin.read().split())\nr = random.Random(seed)\nprint(''.join(r.choice('ab') for _ in range(r.randint(1, size))))\n",
    "tree": "import sys, random\nseed, size = map(int, sys.stdin.read().split())\nr = random.Random(seed)\nn = r.randint(2, size + 1)\nprint(n)\nfor v in range(2, n + 1):\n    print(r.randint(1, v - 1), v)\n",
    "graph": "import sys, random\nseed, size = map(int, sys.stdin.read().split())\nr = random.Random(seed)\nn = r.randint(2, size + 1)\nm = r.randint(1, n * (n - 1) // 2)\nedges = {(min(a, b), max(a, b)) for a, b in ((r.randint(1, n), r.randint(1, n)) for _ in range(m)) if a != b} or {(1, 2)}\nprint(n, len(edges))\nfor a, b in sorted(edges):\n    print(a, b)\n",
}


class StressIn(BaseModel):
    solution_language: str
    solution_code: str = _P
    brute_language: str
    brute_code: str = _P
    generator_code: str = _P  # always Python; reads "<seed> <size>"
    max_size: int = Field(8, ge=1, le=30)
    iterations: int = Field(120, ge=1, le=400)


@router.get("/stress/generators")
def generators(user: User = Depends(current_user)):
    return {"contract": "A generator reads one line '<seed> <size>' from stdin and prints ONE test input. Use the seed for all randomness; size bounds the input size.", "templates": GENERATORS}


@router.post("/stress")
def stress_test(body: StressIn, user: User = Depends(current_user)):
    for lang in (body.solution_language, body.brute_language):
        if lang not in runner.LANGS:
            raise HTTPException(422, f"language must be one of {list(runner.LANGS)}")
    from app.core.config import get_settings
    limiter.check(f"stress:{user.id}", 3, 60.0)
    if get_settings().executor_url:  # run on the executor host: the API never touches Docker
        from app.execution import remote
        try:
            return remote.stress(body.model_dump())
        except remote.BusyError:
            raise HTTPException(429, "The execution workers are busy. Try again in a few seconds.", headers={"Retry-After": "3"}) from None
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from None
    if not _SLOTS.acquire(blocking=False):
        raise HTTPException(429, "The execution workers are busy. Try again in a few seconds.", headers={"Retry-After": "3"})
    try:
        return stress.run((body.solution_language, body.solution_code), (body.brute_language, body.brute_code), ("python", body.generator_code), body.max_size, 40.0, body.iterations)
    finally:
        _SLOTS.release()

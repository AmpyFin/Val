from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List

app = FastAPI(title="Val Strategy Service")

class StrategyEvalItem(BaseModel):
    ticker: str
    data: Dict[str, Any] = Field(..., description="e.g., {'eps_ttm': 2.4, 'growth_5y_est': 0.12}")

class StrategyEvalRequest(BaseModel):
    strategy: str
    items: List[StrategyEvalItem]

class StrategyResultModel(BaseModel):
    fair_value: float
    inputs: Dict[str, Any]
    notes: str = ""
    conf: float = 1.0

class StrategyEvalItemResponse(BaseModel):
    ticker: str
    result: StrategyResultModel

class StrategyEvalResponse(BaseModel):
    items: List[StrategyEvalItemResponse]

def eval_peter_lynch(items: List[StrategyEvalItem]) -> List[StrategyEvalItemResponse]:
    out: List[StrategyEvalItemResponse] = []
    for it in items:
        d = it.data
        if "eps_ttm" not in d or "growth_5y_est" not in d:
            raise HTTPException(status_code=400, detail=f"Missing 'eps_ttm' or 'growth_5y_est' for {it.ticker}")
        eps = float(d["eps_ttm"])
        growth = max(0.0, float(d["growth_5y_est"]))
        fair_pe = min(40.0, growth * 100.0)
        fair_value = max(0.0, eps * fair_pe)
        out.append(StrategyEvalItemResponse(
            ticker=it.ticker,
            result=StrategyResultModel(
                fair_value=fair_value,
                inputs={"eps_ttm": eps, "growth": growth, "fair_pe": fair_pe},
                notes="PEG≈1 fair PE heuristic",
                conf=0.7 if growth > 0 else 0.3
            )
        ))
    return out

STRATS = {
    "peter_lynch": eval_peter_lynch,
}

@app.get("/health")
def health():
    return {"status": "ok", "service": "strategy", "version": "0.0.2"}

@app.post("/eval", response_model=StrategyEvalResponse)
def eval_strategy(req: StrategyEvalRequest):
    fn = STRATS.get(req.strategy)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Unknown strategy '{req.strategy}'")
    return StrategyEvalResponse(items=fn(req.items))

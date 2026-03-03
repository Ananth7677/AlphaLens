# agents/scorer_agent/scorecard_builder.py
"""
Scorecard Builder

Aggregates individual dimension scores into final scorecard:
1. Fetches financial data from database
2. Calculates all dimension scores
3. Computes weighted overall score
4. Stores result in scorecard table

Default Weights:
- Financial Health: 25%
- Growth: 20%
- Valuation: 20%
- Moat: 20%
- Predictability: 15%
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .financial_health import calculate_financial_health_score
from .growth_scorer import calculate_growth_score
from .valuation_scorer import calculate_valuation_score
from .moat_scorer import calculate_moat_score
from .predictability_scorer import calculate_predictability_score


# Default scoring weights
DEFAULT_WEIGHTS = {
    "financial_health": 0.25,
    "growth": 0.20,
    "valuation": 0.20,
    "moat": 0.20,
    "predictability": 0.15
}


def build_scorecard(ticker: str, scores: dict, weights: dict = None) -> dict:
    """
    Build scorecard from pre-calculated dimension scores (synchronous helper).
    
    Args:
        ticker: Stock ticker symbol
        scores: Dict with dimension scores (financial_health_score, growth_score, etc.)
        weights: Optional custom weights for dimensions
    
    Returns:
        Dict with all scores and overall rating
    """
    if weights is None or not weights:
        weights = DEFAULT_WEIGHTS.copy()
    
    # Map score keys to weight keys
    score_mapping = {
        'financial_health_score': 'financial_health',
        'growth_score': 'growth',
        'valuation_score': 'valuation',
        'moat_score': 'moat',
        'predictability_score': 'predictability'
    }
    
    # Calculate weighted overall score
    total_weight = 0
    weighted_sum = 0
    
    for score_key, weight_key in score_mapping.items():
        if score_key in scores and scores[score_key] is not None:
            weight = weights.get(weight_key, 0)
            weighted_sum += scores[score_key] * weight
            total_weight += weight
    
    overall_score = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0
    
    # Determine recommendation based on overall score
    if overall_score >= 75:
        recommendation = "STRONG BUY"
    elif overall_score >= 60:
        recommendation = "BUY"
    elif overall_score >= 40:
        recommendation = "HOLD"
    elif overall_score >= 25:
        recommendation = "SELL"
    else:
        recommendation = "STRONG SELL"
    
    return {
        "ticker": ticker,
        "overall_score": overall_score,
        "recommendation": recommendation,
        **scores  # Include all individual dimension scores
    }


async def build_scorecard_from_db(
    db: AsyncSession,
    ticker: str,
    weights: dict = None
) -> Optional[dict]:
    """
    Build complete scorecard for ticker.
    
    Args:
        db: Database session
        ticker: Stock ticker symbol
        weights: Optional custom weights for dimensions
    
    Returns:
        Dict with all scores and overall rating, or None if insufficient data
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    
    # 1. Fetch current financial data
    from src.dbo.repositories import financials_repo
    
    financials = await financials_repo.get_latest(db, ticker)
    if not financials:
        return None
    
    # Convert SQLAlchemy model to dict
    financial_data = _model_to_dict(financials)
    
    # 2. Fetch historical data (for growth and predictability)
    historical = await financials_repo.get_historical(db, ticker, limit=5)
    historical_data = [_model_to_dict(h) for h in historical] if historical else []
    
    # 3. Calculate dimension scores
    health_result = calculate_financial_health_score(financial_data)
    growth_result = calculate_growth_score(financial_data, historical_data)
    valuation_result = calculate_valuation_score(financial_data)
    moat_result = calculate_moat_score(financial_data)
    predictability_result = calculate_predictability_score(financial_data, historical_data)
    
    # 4. Extract scores
    dimension_scores = {}
    score_details = {}
    
    if health_result.get("score") is not None:
        dimension_scores["financial_health"] = health_result["score"]
        score_details["financial_health"] = health_result
    
    if growth_result.get("score") is not None:
        dimension_scores["growth"] = growth_result["score"]
        score_details["growth"] = growth_result
    
    if valuation_result.get("score") is not None:
        dimension_scores["valuation"] = valuation_result["score"]
        score_details["valuation"] = valuation_result
    
    if moat_result.get("score") is not None:
        dimension_scores["moat"] = moat_result["score"]
        score_details["moat"] = moat_result
    
    if predictability_result.get("score") is not None:
        dimension_scores["predictability"] = predictability_result["score"]
        score_details["predictability"] = predictability_result
    
    # 5. Calculate overall score (weighted average)
    if not dimension_scores:
        return None
    
    # Adjust weights for available dimensions
    available_weights = {k: weights[k] for k in dimension_scores if k in weights}
    total_weight = sum(available_weights.values())
    
    if total_weight == 0:
        return None
    
    # Normalize weights to sum to 1.0
    normalized_weights = {k: v / total_weight for k, v in available_weights.items()}
    
    # Calculate weighted score
    overall_score = sum(
        dimension_scores[dim] * normalized_weights[dim]
        for dim in dimension_scores
    )
    
    # 6. Build scorecard dict
    scorecard = {
        "ticker": ticker,
        "financial_health_score": int(dimension_scores.get("financial_health")) if dimension_scores.get("financial_health") is not None else None,
        "growth_score": int(dimension_scores.get("growth")) if dimension_scores.get("growth") is not None else None,
        "valuation_score": int(dimension_scores.get("valuation")) if dimension_scores.get("valuation") is not None else None,
        "moat_score": int(dimension_scores.get("moat")) if dimension_scores.get("moat") is not None else None,
        "predictability_score": int(dimension_scores.get("predictability")) if dimension_scores.get("predictability") is not None else None,
        "overall_score": int(round(overall_score)),
        "generated_at": datetime.now(timezone.utc)
    }
    
    # 7. Store in database
    from src.dbo.repositories import scorecard_repo
    await scorecard_repo.upsert(db, scorecard)
    await db.commit()
    
    return scorecard


def _model_to_dict(model) -> dict:
    """Convert SQLAlchemy model to dict."""
    if model is None:
        return {}
    
    result = {}
    for column in model.__table__.columns:
        value = getattr(model, column.name)
        # Convert Decimal to float for calculations
        if value is not None and hasattr(value, '__float__'):
            value = float(value)
        result[column.name] = value
    
    return result


def get_rating_label(score: float) -> str:
    """
    Convert numeric score to rating label.
    
    Args:
        score: Overall score (0-100)
    
    Returns:
        Rating label (Strong Buy, Buy, Hold, Sell, Strong Sell)
    """
    if score >= 80:
        return "Strong Buy"
    elif score >= 65:
        return "Buy"
    elif score >= 50:
        return "Hold"
    elif score >= 35:
        return "Sell"
    else:
        return "Strong Sell"

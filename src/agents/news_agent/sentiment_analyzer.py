# agents/news_agent/sentiment_analyzer.py
"""
Sentiment analyzer using Google Gemini API.

Analyzes news article titles and descriptions to determine sentiment:
- positive (score > 0.3)
- neutral (score -0.3 to 0.3)
- negative (score < -0.3)

Score ranges from -1.0 (very negative) to +1.0 (very positive).
"""

import os
from google import genai
from typing import Dict


# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None


async def analyze_sentiment(title: str, description: str = "") -> Dict[str, any]:
    """
    Analyze sentiment of a news article using Gemini.
    
    Args:
        title: Article title
        description: Article description/summary (optional)
    
    Returns:
        dict with sentiment (positive/neutral/negative), confidence, and score
    """
    if not GEMINI_API_KEY or not client:
        # Fallback to simple keyword-based sentiment if no API key
        return _simple_sentiment(title, description)
    
    try:
        # Combine title and description
        text = f"{title}. {description}".strip()
        if not text:
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "score": 0.0
            }
        
        # Build prompt for Gemini
        prompt = f"""Analyze the sentiment of this news headline about a stock/company.

News: {text}

Provide sentiment analysis in this exact format:
SENTIMENT: [positive/neutral/negative]
SCORE: [number from -1.0 to 1.0, where -1 is very negative, 0 is neutral, 1 is very positive]
CONFIDENCE: [number from 0.0 to 1.0]

Consider:
- positive: good earnings, growth, partnerships, product launches, analyst upgrades
- negative: losses, layoffs, lawsuits, scandals, downgrades, regulatory issues
- neutral: routine announcements, factual reporting without clear positive/negative spin

Be concise and provide only the three values above."""

        # Call Gemini API
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        
        # Parse response
        sentiment_data = _parse_gemini_response(response.text)
        return sentiment_data
    
    except Exception as e:
        print(f"Warning: Gemini sentiment analysis failed: {e}")
        # Fallback to simple sentiment
        return _simple_sentiment(title, description)


def _parse_gemini_response(response_text: str) -> Dict[str, any]:
    """
    Parse Gemini API response to extract sentiment, score, and confidence.
    
    Args:
        response_text: Raw text from Gemini
    
    Returns:
        dict with sentiment, score, confidence
    """
    try:
        lines = response_text.strip().split('\n')
        sentiment = "neutral"
        score = 0.0
        confidence = 0.5
        
        for line in lines:
            line = line.strip().upper()
            if line.startswith("SENTIMENT:"):
                sentiment_value = line.split(":", 1)[1].strip().lower()
                if sentiment_value in ["positive", "neutral", "negative"]:
                    sentiment = sentiment_value
            elif line.startswith("SCORE:"):
                try:
                    score = float(line.split(":", 1)[1].strip())
                    # Clamp to [-1, 1]
                    score = max(-1.0, min(1.0, score))
                except ValueError:
                    pass
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                    # Clamp to [0, 1]
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    pass
        
        return {
            "sentiment": sentiment,
            "score": score,
            "confidence": confidence
        }
    
    except Exception as e:
        print(f"Warning: Failed to parse Gemini response: {e}")
        return {
            "sentiment": "neutral",
            "score": 0.0,
            "confidence": 0.0
        }


def _simple_sentiment(title: str, description: str = "") -> Dict[str, any]:
    """
    Simple keyword-based sentiment analysis (fallback when Gemini unavailable).
    
    Args:
        title: Article title
        description: Article description
    
    Returns:
        dict with sentiment, score, confidence
    """
    text = f"{title} {description}".lower()
    
    # Positive keywords
    positive_words = [
        "beat", "exceeds", "soars", "surge", "rally", "gain", "profit",
        "growth", "strong", "upgrade", "buy", "bullish", "record",
        "partnership", "innovation", "success", "positive", "boost"
    ]
    
    # Negative keywords
    negative_words = [
        "miss", "falls", "plunge", "crash", "loss", "decline", "weak",
        "downgrade", "sell", "bearish", "lawsuit", "scandal", "probe",
        "investigation", "layoff", "cut", "warning", "concern", "risk"
    ]
    
    # Count matches
    positive_count = sum(1 for word in positive_words if word in text)
    negative_count = sum(1 for word in negative_words if word in text)
    
    # Calculate score
    if positive_count > negative_count:
        score = min(0.7, positive_count * 0.2)
        sentiment = "positive"
        confidence = min(0.8, (positive_count - negative_count) * 0.15)
    elif negative_count > positive_count:
        score = max(-0.7, -negative_count * 0.2)
        sentiment = "negative"
        confidence = min(0.8, (negative_count - positive_count) * 0.15)
    else:
        score = 0.0
        sentiment = "neutral"
        confidence = 0.5
    
    return {
        "sentiment": sentiment,
        "score": score,
        "confidence": confidence
    }

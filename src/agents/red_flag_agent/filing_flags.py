# agents/red_flag_agent/filing_flags.py
"""
SEC Filing Red Flag Analyzer

Analyzes SEC filing text for warning signs:
1. Increasing risk disclosures
2. Legal issues and litigation
3. Management changes
4. Audit concerns and restatements
5. Regulatory investigations

Note: Requires SEC chunks from RAG agent.
Returns empty list if no filings available.
"""

from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession


async def detect_filing_flags(db: AsyncSession, ticker: str) -> List[dict]:
    """
    Detect red flags from SEC filing text.
    
    Analyzes most recent filings for concerning language patterns.
    Returns list of flag dicts.
    """
    flags = []
    
    try:
        # Get recent SEC filings
        from src.dbo.repositories import sec_repo
        
        recent_filings = await sec_repo.get_recent_filings(db, ticker, limit=3)
        
        if not recent_filings:
            return flags  # No filings available
        
        # Analyze each filing
        for filing in recent_filings:
            # Get chunks for this filing
            chunks = await sec_repo.get_chunks_by_filing(db, filing.id)
            
            if not chunks:
                continue
            
            # Combine Risk Factors section text
            risk_text = ""
            legal_text = ""
            md_and_a_text = ""
            
            for chunk in chunks:
                section = chunk.section_type or ""
                text = chunk.chunk_text or ""
                
                if "risk" in section.lower():
                    risk_text += text + " "
                elif "legal" in section.lower() or "litigation" in section.lower():
                    legal_text += text + " "
                elif "md&a" in section.lower() or "management" in section.lower():
                    md_and_a_text += text + " "
            
            # Analyze risk disclosures
            risk_flags = _analyze_risk_disclosures(risk_text, filing.filing_type)
            flags.extend(risk_flags)
            
            # Analyze legal issues
            legal_flags = _analyze_legal_issues(legal_text + md_and_a_text)
            flags.extend(legal_flags)
            
            # Analyze management discussion
            mgmt_flags = _analyze_management_discussion(md_and_a_text)
            flags.extend(mgmt_flags)
    
    except Exception as e:
        # Silently skip filing analysis if errors occur
        pass
    
    return flags


def _analyze_risk_disclosures(text: str, filing_type: str) -> List[dict]:
    """Analyze risk factor section for warning signs."""
    flags = []
    
    if not text or len(text) < 100:
        return flags
    
    text_lower = text.lower()
    
    # Check for litigation/legal risks
    if "litigation" in text_lower or "lawsuit" in text_lower or "legal proceedings" in text_lower:
        count = text_lower.count("litigation") + text_lower.count("lawsuit")
        if count > 3:
            flags.append({
                "category": "FILING",
                "severity": "HIGH",
                "flag_type": "LITIGATION_RISK",
                "description": f"Multiple mentions of litigation/lawsuits in {filing_type} risk factors. Active legal issues."
            })
    
    # Check for regulatory risks
    if "regulatory" in text_lower or "investigation" in text_lower or "sec" in text_lower:
        if "investigation" in text_lower:
            flags.append({
                "category": "FILING",
                "severity": "HIGH",
                "flag_type": "REGULATORY_INVESTIGATION",
                "description": f"Mentions regulatory investigation in {filing_type}. Potential compliance issues."
            })
        elif text_lower.count("regulatory") > 5:
            flags.append({
                "category": "FILING",
                "severity": "MEDIUM",
                "flag_type": "REGULATORY_RISK",
                "description": f"Significant regulatory risk disclosures in {filing_type}."
            })
    
    # Check for going concern language
    if "going concern" in text_lower or "substantial doubt" in text_lower:
        flags.append({
            "category": "FILING",
            "severity": "HIGH",
            "flag_type": "GOING_CONCERN",
            "description": f"Going concern language in {filing_type}. Auditor questions company's viability."
        })
    
    # Check for cybersecurity incidents
    if "breach" in text_lower or "cyber attack" in text_lower or "data breach" in text_lower:
        flags.append({
            "category": "FILING",
            "severity": "MEDIUM",
            "flag_type": "CYBERSECURITY_INCIDENT",
            "description": f"Mentions cybersecurity breach or attack in {filing_type}."
        })
    
    return flags


def _analyze_legal_issues(text: str) -> List[dict]:
    """Analyze for legal and litigation issues."""
    flags = []
    
    if not text or len(text) < 100:
        return flags
    
    text_lower = text.lower()
    
    # Check for class action lawsuits
    if "class action" in text_lower:
        flags.append({
            "category": "FILING",
            "severity": "HIGH",
            "flag_type": "CLASS_ACTION",
            "description": "Class action lawsuit mentioned. Potential material liability."
        })
    
    # Check for government investigations
    if "department of justice" in text_lower or "doj" in text_lower or "ftc" in text_lower:
        flags.append({
            "category": "FILING",
            "severity": "HIGH",
            "flag_type": "GOVERNMENT_INVESTIGATION",
            "description": "Government investigation by DOJ/FTC mentioned."
        })
    
    # Check for settlements
    if "settlement" in text_lower and ("million" in text_lower or "billion" in text_lower):
        flags.append({
            "category": "FILING",
            "severity": "MEDIUM",
            "flag_type": "LARGE_SETTLEMENT",
            "description": "Large legal settlement mentioned. Material financial impact."
        })
    
    return flags


def _analyze_management_discussion(text: str) -> List[dict]:
    """Analyze MD&A for warning signs."""
    flags = []
    
    if not text or len(text) < 100:
        return flags
    
    text_lower = text.lower()
    
    # Check for management changes
    if ("ceo" in text_lower or "chief executive" in text_lower) and ("resign" in text_lower or "departure" in text_lower or "stepping down" in text_lower):
        flags.append({
            "category": "FILING",
            "severity": "MEDIUM",
            "flag_type": "CEO_DEPARTURE",
            "description": "CEO resignation or departure mentioned. Leadership change in progress."
        })
    
    if ("cfo" in text_lower or "chief financial" in text_lower) and ("resign" in text_lower or "departure" in text_lower):
        flags.append({
            "category": "FILING",
            "severity": "MEDIUM",
            "flag_type": "CFO_DEPARTURE",
            "description": "CFO resignation or departure mentioned. Financial leadership change."
        })
    
    # Check for restatements
    if "restatement" in text_lower or "restate" in text_lower:
        flags.append({
            "category": "FILING",
            "severity": "HIGH",
            "flag_type": "FINANCIAL_RESTATEMENT",
            "description": "Financial restatement mentioned. Accounting errors or irregularities."
        })
    
    # Check for internal control weaknesses
    if "material weakness" in text_lower or "internal control" in text_lower and "deficiency" in text_lower:
        flags.append({
            "category": "FILING",
            "severity": "HIGH",
            "flag_type": "INTERNAL_CONTROL_WEAKNESS",
            "description": "Material weakness in internal controls disclosed. Accounting reliability concerns."
        })
    
    # Check for auditor changes
    if "change" in text_lower and ("auditor" in text_lower or "accounting firm" in text_lower):
        if "disagreement" in text_lower:
            flags.append({
                "category": "FILING",
                "severity": "HIGH",
                "flag_type": "AUDITOR_DISAGREEMENT",
                "description": "Auditor change with disagreement mentioned. Potential accounting issues."
            })
        else:
            flags.append({
                "category": "FILING",
                "severity": "LOW",
                "flag_type": "AUDITOR_CHANGE",
                "description": "Auditor change mentioned. Monitor for reasons."
            })
    
    return flags

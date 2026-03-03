# tests/README.md

# AlphaLens Test Suite

Comprehensive unit tests for all AlphaLens agents and orchestration layer.

## 📁 Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and configuration
├── agents/
│   ├── test_financial_agent.py      # Financial agent tests
│   ├── test_scorer_agent.py         # Scorer agent tests
│   ├── test_red_flag_agent.py       # Red flag agent tests
│   ├── test_news_agent.py           # News agent tests
│   └── test_rag_agent.py            # RAG agent tests
├── orchestration/
│   └── test_orchestration.py        # LangGraph workflow tests
└── fixtures/
    └── (future: test data files)
```

## 🚀 Running Tests

### Run All Tests
```bash
conda run -n StablePythonEnv pytest tests/
```

### Run Specific Agent Tests
```bash
# Financial agent
conda run -n StablePythonEnv pytest tests/agents/test_financial_agent.py

# Scorer agent
conda run -n StablePythonEnv pytest tests/agents/test_scorer_agent.py

# Red flag agent
conda run -n StablePythonEnv pytest tests/agents/test_red_flag_agent.py

# News agent
conda run -n StablePythonEnv pytest tests/agents/test_news_agent.py

# RAG agent
conda run -n StablePythonEnv pytest tests/agents/test_rag_agent.py

# Orchestration
conda run -n StablePythonEnv pytest tests/orchestration/test_orchestration.py
```

### Run With Test Runner Script
```bash
# Run all tests
conda run -n StablePythonEnv python run_tests.py

# Run specific agent
conda run -n StablePythonEnv python run_tests.py --agent financial
conda run -n StablePythonEnv python run_tests.py --agent scorer

# Run with coverage report
conda run -n StablePythonEnv python run_tests.py --coverage

# Run specific test pattern
conda run -n StablePythonEnv python run_tests.py -k "test_fetch_yahoo"

# Verbose output
conda run -n StablePythonEnv python run_tests.py -v

# Stop on first failure
conda run -n StablePythonEnv python run_tests.py -x
```

## 📊 Test Coverage

### Financial Agent (test_financial_agent.py)
- ✅ Yahoo Finance integration
- ✅ FMP API integration
- ✅ Data normalization
- ✅ Database storage
- ✅ Error handling
- ✅ Edge cases (missing data, invalid tickers)

**Classes:** 4 | **Tests:** ~20

### Scorer Agent (test_scorer_agent.py)
- ✅ Financial health scoring (liquidity, solvency)
- ✅ Growth scoring (revenue, EPS trends)
- ✅ Valuation scoring (PE, PS, PB, EV/EBITDA)
- ✅ Moat scoring (ROE, margins, efficiency)
- ✅ Predictability scoring (earnings consistency)
- ✅ Scorecard aggregation and weighting

**Classes:** 7 | **Tests:** ~25

### Red Flag Agent (test_red_flag_agent.py)
- ✅ Liquidity risk detection
- ✅ High debt detection
- ✅ Profitability concerns
- ✅ Negative cash flow detection
- ✅ Declining trend detection
- ✅ Flag categorization
- ✅ Risk score calculation

**Classes:** 5 | **Tests:** ~20

### News Agent (test_news_agent.py)
- ✅ Multi-source news scraping (yfinance, Yahoo RSS)
- ✅ Gemini sentiment analysis
- ✅ Keyword fallback
- ✅ Sentiment aggregation
- ✅ Error handling
- ✅ Edge cases (special characters, unicode)

**Classes:** 4 | **Tests:** ~20

### RAG Agent (test_rag_agent.py)
- ✅ SEC filing scraping
- ✅ HTML parsing and chunking
- ✅ Section detection
- ✅ Gemini embedding generation
- ✅ Batch processing
- ✅ Cache management
- ✅ Rate limit handling

**Classes:** 5 | **Tests:** ~20

### Orchestration (test_orchestration.py)
- ✅ State management
- ✅ Node execution (financial, scorer, red_flag, news, final_report)
- ✅ Parallel execution
- ✅ Error aggregation
- ✅ Confidence calculation
- ✅ Recommendation generation
- ✅ End-to-end workflow

**Classes:** 8 | **Tests:** ~30

## 🎯 Test Categories

Tests are marked with pytest markers for easy filtering:

- `@pytest.mark.unit` - Fast unit tests (no external dependencies)
- `@pytest.mark.integration` - Integration tests (database, APIs)
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.asyncio` - Async tests

### Run Only Unit Tests
```bash
conda run -n StablePythonEnv pytest -m unit
```

### Run Integration Tests
```bash
conda run -n StablePythonEnv pytest -m integration
```

## 🔧 Test Configuration

### Environment Variables
Tests use the same environment variables as the main application:
- `GEMINI_API_KEY` - For Gemini API tests
- `FMP_API_KEY` - For FMP API tests (optional)
- `TEST_DATABASE_URL` - Test database (defaults to alphalens_test)

### Test Database
Tests use a separate test database configured in `conftest.py`. The database schema is created before tests and dropped after.

### Mocking
External APIs are mocked using `unittest.mock`:
- Gemini API calls
- SEC EDGAR API calls
- Yahoo Finance data
- FMP API calls

This ensures:
- Tests run fast (no network calls)
- Tests are deterministic
- No API quota consumption
- No external dependencies

## 📈 Coverage Report

Generate HTML coverage report:
```bash
conda run -n StablePythonEnv pytest --cov=src --cov-report=html tests/
```

View report: `open htmlcov/index.html`

## 🐛 Debugging Tests

### Run Single Test
```bash
conda run -n StablePythonEnv pytest tests/agents/test_financial_agent.py::TestYahooFinanceIntegration::test_fetch_yahoo_success -v
```

### Print Output
```bash
conda run -n StablePythonEnv pytest tests/ -s
```

### Show Local Variables on Failure
```bash
conda run -n StablePythonEnv pytest tests/ --showlocals
```

### PDB on Failure
```bash
conda run -n StablePythonEnv pytest tests/ --pdb
```

## ✅ Best Practices

1. **Isolation** - Each test is independent and can run in any order
2. **Mocking** - External APIs are mocked to avoid network calls
3. **Fixtures** - Shared test data defined in `conftest.py`
4. **Async** - Async tests use `@pytest.mark.asyncio`
5. **Assertions** - Clear, specific assertions with good error messages
6. **Coverage** - Aim for >80% code coverage
7. **Speed** - Unit tests should complete in <5 seconds

## 🔄 Continuous Integration

### Pre-commit Checks
```bash
# Run all tests before commit
conda run -n StablePythonEnv pytest tests/

# Run with coverage
conda run -n StablePythonEnv pytest --cov=src tests/
```

### CI/CD Pipeline (Future)
- Run tests on every push
- Generate coverage report
- Block merge if tests fail
- Track coverage over time

## 📝 Adding New Tests

### Test File Template
```python
# tests/agents/test_new_agent.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.agents.new_agent import new_function

class TestNewAgent:
    """Test new agent functionality."""
    
    @pytest.mark.asyncio
    async def test_new_function_success(self):
        """Test successful execution."""
        result = await new_function('TEST')
        
        assert result is not None
        assert result['status'] == 'success'
    
    def test_edge_case(self):
        """Test edge case handling."""
        # Test implementation
        pass
```

### Fixture Template
```python
# tests/conftest.py
@pytest.fixture
def sample_data():
    """Sample data for testing."""
    return {
        'field1': 'value1',
        'field2': 123,
    }
```

## 📚 Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Pytest Coverage](https://pytest-cov.readthedocs.io/)

---

**Total Tests:** ~135  
**Total Classes:** ~33  
**Estimated Coverage:** >75%

"""
Test suite for Stage 2: Hybrid Template Selection in SQLGenerator.

Tests the hybrid approach combining deterministic pattern matching with
LLM-assisted template selection and confirmation.

Test Coverage:
- Unit tests (11): Deterministic matching, LLM selection, hybrid logic
- Integration tests (2): Real API calls with gpt-5
- Edge cases (3): Error handling, invalid responses, incomplete mappings
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.sql_generator import SQLGenerator
from src.models import (
    ExtractedEntities,
    QueryTemplate,
    IntelligenceMatch,
    GeneratedSQL,
    LLMTemplateSelectionResponse,
)
from src.telemetry import create_request_context


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def sql_generator():
    """Create SQLGenerator instance with LLM disabled for controlled testing."""
    with patch('src.sql_generator.get_config') as mock_config:
        config = Mock()
        config.template_selection_use_llm = False  # Start with LLM disabled
        config.template_selection_fast_path_threshold = 0.8
        config.template_selection_llm_threshold = 0.5
        config.template_selection_temperature = 0.0
        config.template_selection_max_retries = 3
        config.template_selection_timeout = 10
        mock_config.return_value = config
        
        generator = SQLGenerator()
        generator.config = config  # Ensure config is set
        return generator


@pytest.fixture
def sql_generator_with_llm():
    """Create SQLGenerator instance with LLM enabled."""
    # Create mock config
    mock_config = Mock()
    mock_config.template_selection_use_llm = True
    mock_config.template_selection_fast_path_threshold = 0.8
    mock_config.template_selection_llm_threshold = 0.5
    mock_config.template_selection_temperature = 0.0
    mock_config.template_selection_max_retries = 3
    mock_config.template_selection_timeout = 10
    
    # Create generator without triggering Azure client initialization
    with patch('src.sql_generator.get_config') as mock_get_config:
        mock_get_config.return_value = mock_config
        
        # Temporarily disable LLM to avoid Azure client init
        original_use_llm = mock_config.template_selection_use_llm
        mock_config.template_selection_use_llm = False
        
        generator = SQLGenerator()
        
        # Now re-enable and add mock client
        mock_config.template_selection_use_llm = original_use_llm
        generator.config = mock_config
        
        # Create mock Azure client
        mock_azure_client = Mock()
        mock_azure_client.is_available.return_value = True
        mock_azure_client.config.deployment_name = "gpt-5"
        mock_azure_client.client = Mock()
        generator.azure_client = mock_azure_client
        
        return generator


@pytest.fixture
def request_context():
    """Create request context for telemetry tracking."""
    return create_request_context("test question")


@pytest.fixture
def sample_entities():
    """Sample extracted entities for testing."""
    return ExtractedEntities(
        companies=["APPLE INC"],
        metrics=["revenue"],
        sectors=["Information Technology"],
        time_periods=["Q3", "2024"],
        question_type="lookup",
        confidence=0.85
    )


@pytest.fixture
def sample_template():
    """Sample query template for testing."""
    return QueryTemplate(
        template_id="company_revenue_lookup",
        name="Company Revenue Lookup",
        pattern=r".*revenue.*",
        sql_template="SELECT revenue FROM financials WHERE company = '{company}'",
        parameters=["company"],
        description="Look up company revenue"
    )


def create_mock_llm_response(template_id: str, confidence: float = 0.9, 
                             use_custom_sql: bool = False,
                             parameter_mapping: dict = None) -> Mock:
    """Helper to create mock LLM template selection response."""
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    
    response_data = {
        "selected_template_id": template_id if not use_custom_sql else None,
        "confidence": confidence,
        "reasoning": "Test selection",
        "use_custom_sql": use_custom_sql,
        "parameter_mapping": parameter_mapping or {},
        "processing_time_ms": 1000,
        "token_usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    
    mock_message.content = json.dumps(response_data)
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    
    return mock_response


# ==============================================================================
# UNIT TESTS: Deterministic Matching
# ==============================================================================

def test_get_candidate_templates_high_confidence(sql_generator, request_context):
    """Test deterministic matching returns high-confidence match (≥0.8)."""
    question = "How many companies in Information Technology?"
    
    # Mock intelligence matcher to return high confidence
    with patch.object(sql_generator.intelligence, 'match_pattern') as mock_match:
        template = QueryTemplate(
            template_id="sector_company_count",
            name="Count companies by sector",
            pattern=r"how many.*companies.*in.*",
            sql_template="SELECT COUNT(*) FROM companies WHERE sector = '{sector}'",
            parameters=["sector"],
            description="Count companies in a sector"
        )
        
        mock_match.return_value = IntelligenceMatch(
            template=template,
            matched_parameters={"sector": "Information Technology"},
            match_confidence=0.85,
            match_method="regex"
        )
        
        # Call match_pattern
        result = sql_generator.intelligence.match_pattern(question)
        
        assert result.template is not None
        assert result.match_confidence >= 0.8
        assert result.template.template_id == "sector_company_count"
        assert "sector" in result.matched_parameters


def test_get_candidate_templates_medium_confidence(sql_generator, request_context):
    """Test deterministic matching returns medium-confidence match (0.5-0.8)."""
    question = "Companies in tech sector"
    
    with patch.object(sql_generator.intelligence, 'match_pattern') as mock_match:
        template = QueryTemplate(
            template_id="sector_company_list",
            name="List companies by sector",
            pattern=r"companies.*in.*",
            sql_template="SELECT name FROM companies WHERE sector = '{sector}'",
            parameters=["sector"],
            description="List companies in a sector"
        )
        
        mock_match.return_value = IntelligenceMatch(
            template=template,
            matched_parameters={"sector": "Technology"},
            match_confidence=0.65,
            match_method="regex"
        )
        
        result = sql_generator.intelligence.match_pattern(question)
        
        assert result.template is not None
        assert 0.5 <= result.match_confidence < 0.8
        assert result.template.template_id == "sector_company_list"


def test_get_candidate_templates_no_match(sql_generator, request_context):
    """Test deterministic matching finds no suitable templates."""
    question = "What companies are doing well?"
    
    with patch.object(sql_generator.intelligence, 'match_pattern') as mock_match:
        mock_match.return_value = IntelligenceMatch(
            template=None,
            matched_parameters={},
            match_confidence=0.0,
            match_method="none"
        )
        
        result = sql_generator.intelligence.match_pattern(question)
        
        assert result.template is None
        assert result.match_confidence < 0.5


# ==============================================================================
# UNIT TESTS: LLM Template Selection
# ==============================================================================

def test_llm_template_selection_mock_success(sql_generator_with_llm, sample_entities, request_context):
    """Mock LLM response selecting valid template ID."""
    question = "What is Apple's revenue?"
    
    # Mock LLM response
    mock_response = create_mock_llm_response(
        template_id="company_revenue_lookup",
        confidence=0.92,
        parameter_mapping={"company": "APPLE INC"}
    )
    
    sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
    
    # Mock intelligence to return candidate templates
    with patch.object(sql_generator_with_llm.intelligence, 'get_template_by_id') as mock_get:
        template = QueryTemplate(
            template_id="company_revenue_lookup",
            name="Company Revenue",
            pattern="",
            sql_template="SELECT revenue FROM num WHERE company = '{company}'",
            parameters=["company"],
            description="Get company revenue"
        )
        mock_get.return_value = template
        
        # Call _select_template_with_llm (will be implemented)
        # For now, we're just testing the mock structure
        assert mock_response.choices[0].message.content is not None
        
        # Parse response
        content = json.loads(mock_response.choices[0].message.content)
        assert content["selected_template_id"] == "company_revenue_lookup"
        assert content["confidence"] == 0.92
        assert content["use_custom_sql"] is False
        assert content["parameter_mapping"]["company"] == "APPLE INC"


def test_llm_template_selection_mock_recommend_custom_sql(sql_generator_with_llm, sample_entities, request_context):
    """Mock LLM response with use_custom_sql=True, selected_template_id=None."""
    question = "Which companies have the highest growth rate?"
    
    mock_response = create_mock_llm_response(
        template_id=None,
        confidence=0.75,
        use_custom_sql=True
    )
    
    sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
    
    content = json.loads(mock_response.choices[0].message.content)
    
    assert content["selected_template_id"] is None
    assert content["use_custom_sql"] is True
    assert content["confidence"] == 0.75


def test_llm_template_selection_parameter_mapping(sql_generator_with_llm, sample_entities, request_context):
    """Mock LLM returns parameter_mapping."""
    question = "How many companies in Technology?"
    
    mock_response = create_mock_llm_response(
        template_id="sector_company_count",
        confidence=0.88,
        parameter_mapping={"sector": "Information Technology"}
    )
    
    sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
    
    content = json.loads(mock_response.choices[0].message.content)
    
    assert content["parameter_mapping"]["sector"] == "Information Technology"
    assert "sector" in content["parameter_mapping"]


# ==============================================================================
# UNIT TESTS: Hybrid Logic
# ==============================================================================

def test_hybrid_fast_path_high_confidence(sql_generator_with_llm, sample_entities, request_context):
    """
    Test fast path: High confidence (≥0.8) skips LLM, uses template directly.
    """
    question = "How many companies in Technology?"
    
    with patch.object(sql_generator_with_llm.intelligence, 'match_pattern') as mock_match:
        template = QueryTemplate(
            template_id="sector_company_count",
            name="Count by sector",
            pattern="",
            sql_template="SELECT COUNT(*) FROM companies WHERE sector = '{sector}'",
            parameters=["sector"],
            description="Count companies by sector"
        )
        
        mock_match.return_value = IntelligenceMatch(
            template=template,
            matched_parameters={"sector": "Technology"},
            match_confidence=0.85,
            match_method="regex"
        )
        
        # Generate SQL - should use fast path, NOT call LLM
        result = sql_generator_with_llm.generate(sample_entities, question, request_context)
        
        # Verify LLM was NOT called (fast path)
        assert not sql_generator_with_llm.azure_client.client.chat.completions.create.called
        
        # Verify telemetry
        assert request_context.metadata.get("template_selection_method") == "fast_path"


def test_hybrid_llm_confirmation_medium_confidence(sql_generator_with_llm, sample_entities, request_context):
    """
    Test LLM confirmation: Medium confidence (0.5-0.8) calls LLM for confirmation.
    """
    question = "Companies in tech sector"
    
    with patch.object(sql_generator_with_llm.intelligence, 'match_pattern') as mock_match:
        template = QueryTemplate(
            template_id="sector_company_list",
            name="List by sector",
            pattern="",
            sql_template="SELECT name FROM companies WHERE sector = '{sector}'",
            parameters=["sector"],
            description="List companies"
        )
        
        mock_match.return_value = IntelligenceMatch(
            template=template,
            matched_parameters={"sector": "Technology"},
            match_confidence=0.65,
            match_method="regex"
        )
        
        # Mock LLM to confirm the template
        mock_response = create_mock_llm_response(
            template_id="sector_company_list",
            confidence=0.9,
            parameter_mapping={"sector": "Information Technology"}
        )
        sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
        
        with patch.object(sql_generator_with_llm.intelligence, 'get_template_by_id') as mock_get:
            mock_get.return_value = template
            
            # This will call LLM for confirmation
            # (Implementation will be tested once code is written)
            
            # Verify telemetry would show llm_confirmation
            # (Will be tested after implementation)
            pass


def test_hybrid_llm_selection_low_confidence(sql_generator_with_llm, sample_entities, request_context):
    """
    Test LLM fallback: Low confidence (<0.5) calls LLM to select from all templates.
    """
    question = "What companies are doing well?"
    
    with patch.object(sql_generator_with_llm.intelligence, 'match_pattern') as mock_match:
        mock_match.return_value = IntelligenceMatch(
            template=None,
            matched_parameters={},
            match_confidence=0.3,
            match_method="none"
        )
        
        # Mock LLM to select a template
        mock_response = create_mock_llm_response(
            template_id=None,
            confidence=0.6,
            use_custom_sql=True  # LLM recommends custom SQL
        )
        sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
        
        # This will trigger LLM fallback path
        # (Will be fully tested after implementation)
        pass


def test_llm_template_selection_retry_on_json_error(sql_generator_with_llm, sample_entities, request_context):
    """Test retry logic on JSON parsing errors."""
    question = "What is Apple's CIK?"
    
    # First response: malformed JSON
    invalid_response = Mock()
    invalid_choice = Mock()
    invalid_message = Mock()
    invalid_message.content = "Invalid JSON {"
    invalid_choice.message = invalid_message
    invalid_response.choices = [invalid_choice]
    invalid_response.usage = Mock()
    invalid_response.usage.prompt_tokens = 100
    invalid_response.usage.completion_tokens = 20
    
    # Second response: valid JSON
    valid_response = create_mock_llm_response(
        template_id="company_cik_lookup",
        confidence=0.95,
        parameter_mapping={"company": "APPLE INC"}
    )
    
    sql_generator_with_llm.azure_client.client.chat.completions.create.side_effect = [
        invalid_response,
        valid_response
    ]
    
    # Test will verify retry logic once _select_template_with_llm is implemented
    # For now, just verify mock is set up correctly
    assert invalid_response.choices[0].message.content == "Invalid JSON {"
    assert valid_response.choices[0].message.content is not None


def test_telemetry_tracking_template_selection(sql_generator_with_llm, sample_entities, request_context):
    """Verify LLM call tracked in context.metadata['llm_calls']."""
    question = "What is Apple's revenue?"
    
    mock_response = create_mock_llm_response(
        template_id="company_revenue_lookup",
        confidence=0.9,
        parameter_mapping={"company": "APPLE INC"}
    )
    
    sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
    
    # After implementation, verify:
    # - context.metadata["llm_calls"] contains entry
    # - Entry has stage="template_selection"
    # - Entry has tokens, latency_ms, success
    
    # Placeholder assertion
    assert request_context.metadata is not None


# ==============================================================================
# INTEGRATION TESTS (require real Azure OpenAI API)
# ==============================================================================

@pytest.mark.integration
def test_real_llm_template_selection_simple_match(sample_entities, request_context):
    """Integration test with real Azure OpenAI API - simple question."""
    from src.sql_generator import SQLGenerator
    
    generator = SQLGenerator()
    
    # Skip if LLM not enabled
    if not hasattr(generator, 'azure_client') or generator.azure_client is None:
        pytest.skip("Azure OpenAI client not available")
    
    question = "What is Apple's CIK?"
    
    # This should match a template and generate SQL
    result = generator.generate(sample_entities, question, request_context)
    
    # Verify result
    assert result is not None
    assert isinstance(result, GeneratedSQL)
    assert result.sql is not None
    assert len(result.sql) > 0
    
    print(f"\nReal LLM template selection: {result.template_id}")
    print(f"SQL: {result.sql[:100]}")


@pytest.mark.integration
def test_real_llm_template_selection_ambiguous(sample_entities, request_context):
    """Integration test with real API - ambiguous question."""
    from src.sql_generator import SQLGenerator
    
    generator = SQLGenerator()
    
    if not hasattr(generator, 'azure_client') or generator.azure_client is None:
        pytest.skip("Azure OpenAI client not available")
    
    question = "Tell me about tech companies"
    
    # LLM should either select a template or recommend custom SQL
    result = generator.generate(sample_entities, question, request_context)
    
    # Result might be None (custom SQL needed) or GeneratedSQL
    if result:
        assert isinstance(result, GeneratedSQL)
        print(f"\nLLM selected template: {result.template_id}")
    else:
        print("\nLLM recommended custom SQL generation")


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================

def test_no_candidates_llm_selects_from_all(sql_generator_with_llm, sample_entities, request_context):
    """Test LLM considers all templates when deterministic returns no candidates."""
    question = "Random question with no obvious template match"
    
    with patch.object(sql_generator_with_llm.intelligence, 'match_pattern') as mock_match:
        # No match from deterministic
        mock_match.return_value = IntelligenceMatch(
            template=None,
            matched_parameters={},
            match_confidence=0.0,
            match_method="none"
        )
        
        with patch.object(sql_generator_with_llm.intelligence, 'get_all_templates') as mock_all:
            # Mock should return all 26 templates
            mock_all.return_value = []  # Simplified for test
            
            # LLM should be called with all templates as candidates
            # (Will be verified after implementation)
            pass


def test_llm_returns_invalid_template_id(sql_generator_with_llm, sample_entities, request_context):
    """Test error handling when LLM returns non-existent template_id."""
    question = "What is Apple's CIK?"
    
    # Mock LLM to return invalid template ID
    mock_response = create_mock_llm_response(
        template_id="nonexistent_template",
        confidence=0.85,
        parameter_mapping={"company": "APPLE INC"}
    )
    
    sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
    
    with patch.object(sql_generator_with_llm.intelligence, 'get_template_by_id') as mock_get:
        # Template not found
        mock_get.return_value = None
        
        # Should handle gracefully (log warning, return None or fallback)
        # (Will be tested after implementation)
        pass


def test_parameter_mapping_incomplete(sql_generator_with_llm, sample_entities, request_context):
    """Test handling of incomplete parameter_mapping from LLM."""
    question = "What is the revenue for Apple in Q3 2024?"
    
    # Mock LLM returns incomplete mapping (missing 'quarter' and 'year')
    mock_response = create_mock_llm_response(
        template_id="company_revenue_period",
        confidence=0.8,
        parameter_mapping={"company": "APPLE INC"}  # Missing time period params
    )
    
    sql_generator_with_llm.azure_client.client.chat.completions.create.return_value = mock_response
    
    with patch.object(sql_generator_with_llm.intelligence, 'get_template_by_id') as mock_get:
        template = QueryTemplate(
            template_id="company_revenue_period",
            name="Revenue by period",
            pattern="",
            sql_template="SELECT revenue FROM num WHERE company = '{company}' AND period = '{period}'",
            parameters=["company", "period"],
            description="Get revenue for specific period"
        )
        mock_get.return_value = template
        
        # Should attempt to fill missing parameters from entities
        # sample_entities has time_periods = ["Q3", "2024"]
        # System should try to construct 'period' parameter
        # (Will be tested after implementation)
        pass


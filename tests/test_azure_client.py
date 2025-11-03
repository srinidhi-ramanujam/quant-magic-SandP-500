"""
Tests for Azure OpenAI Client Wrapper

Comprehensive test suite covering initialization, SQL generation, analysis,
embeddings, error handling, retry logic, and Pydantic validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.azure_client import AzureOpenAIClient, get_azure_client
from src.models import (
    LLMConfig,
    LLMRequest,
    LLMResponse,
    LLMAnalysisRequest,
    LLMAnalysisResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    QueryComplexity,
)


class TestAzureClientInitialization:
    """Test client initialization and configuration."""
    
    def test_init_with_config(self):
        """Test client initialization with provided config."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345",
            deployment_name="gpt-5-test"
        )
        
        with patch('src.azure_client.OpenAI') as mock_openai:
            client = AzureOpenAIClient(config=config)
            
            assert client.config == config
            assert client.config.deployment_name == "gpt-5-test"
    
    def test_init_without_config(self):
        """Test client initialization loading from environment."""
        with patch.dict('os.environ', {
            'AZURE_OPENAI_ENDPOINT': 'https://env.openai.azure.com/',
            'AZURE_OPENAI_API_KEY': 'env-key-123',
            'AZURE_OPENAI_DEPLOYMENT_NAME': 'gpt-4'
        }):
            with patch('src.azure_client.OpenAI'):
                client = AzureOpenAIClient()
                
                assert client.config.azure_endpoint == 'https://env.openai.azure.com/'
                assert client.config.deployment_name == 'gpt-4'
    
    def test_is_available_when_initialized(self):
        """Test is_available returns True when client initialized."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI'):
            client = AzureOpenAIClient(config=config)
            client.client = Mock()  # Mock initialized client
            
            assert client.is_available() is True
    
    def test_is_available_when_not_initialized(self):
        """Test is_available returns False when client not initialized."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI', side_effect=Exception("Init failed")):
            client = AzureOpenAIClient(config=config)
            
            assert client.is_available() is False
    
    def test_circuit_breaker_triggered(self):
        """Test circuit breaker prevents calls after threshold failures."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI'):
            client = AzureOpenAIClient(config=config)
            client.client = Mock()
            client._circuit_breaker_failures = 5  # At threshold
            
            assert client.is_available() is False


class TestSQLGeneration:
    """Test SQL generation functionality."""
    
    def test_generate_sql_success(self):
        """Test successful SQL generation."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345",
            deployment_name="gpt-5"
        )
        
        # Mock API response
        mock_response = Mock()
        mock_response.output_text = "```sql\nSELECT COUNT(*) FROM companies WHERE gics_sector = 'Technology';\n```\nThis query counts companies in the Technology sector."
        mock_response.usage = Mock(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            output_tokens_details=Mock(reasoning_tokens=30)
        )
        
        with patch('src.azure_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_client.responses.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            client = AzureOpenAIClient(config=config)
            client.client = mock_client
            
            request = LLMRequest(query="How many companies in Technology sector?")
            response = client.generate_sql(request)
            
            assert response.success is True
            assert response.generated_sql is not None
            assert "SELECT" in response.generated_sql.upper()
            assert response.confidence > 0.5
            assert response.token_usage['total_tokens'] == 150
            assert response.token_usage['reasoning_tokens'] == 30
    
    def test_generate_sql_client_not_available(self):
        """Test SQL generation when client not available."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI', side_effect=Exception("Init failed")):
            client = AzureOpenAIClient(config=config)
            
            request = LLMRequest(query="Test query")
            response = client.generate_sql(request)
            
            assert response.success is False
            assert "not available" in response.explanation.lower()
            assert response.confidence == 0.0
    
    def test_generate_sql_with_context(self):
        """Test SQL generation with additional context."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        mock_response = Mock()
        mock_response.output_text = "SELECT * FROM companies WHERE cik = '0001418121';"
        mock_response.usage = Mock(input_tokens=50, output_tokens=25, total_tokens=75)
        
        with patch('src.azure_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_client.responses.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            client = AzureOpenAIClient(config=config)
            client.client = mock_client
            
            request = LLMRequest(
                query="What is Apple's CIK?",
                context={"company": "Apple Inc", "cik": "0001418121"}
            )
            response = client.generate_sql(request)
            
            assert response.success is True


class TestQueryAnalysis:
    """Test query analysis functionality."""
    
    def test_analyze_query_success(self):
        """Test successful query analysis."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        mock_response = Mock()
        mock_response.output_text = """
Recommended approach: Use JOIN between companies and num tables.
This is a medium complexity query requiring ratio calculations.
Required tables: companies, num
"""
        
        with patch('src.azure_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_client.responses.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            client = AzureOpenAIClient(config=config)
            client.client = mock_client
            
            request = LLMAnalysisRequest(
                failed_query="Which companies have highest profit margins?",
                failure_context={"error": "No template match"},
                available_templates=["financial_ratios"],
                schema_info={"tables": ["companies", "num"]}
            )
            
            response = client.analyze_query(request)
            
            assert response.analysis_success is True
            assert "JOIN" in response.recommended_approach
            # Complexity can be MEDIUM or COMPLEX based on content
            assert response.identified_complexity in [QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]
            assert "companies" in response.required_tables or "num" in response.required_tables


class TestEmbeddings:
    """Test embeddings generation functionality."""
    
    def test_generate_embeddings_success(self):
        """Test successful embeddings generation."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345",
            embeddings_deployment="text-embedding-ada-002"
        )
        
        mock_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
        mock_response = Mock()
        mock_response.data = [Mock(embedding=mock_embedding)]
        mock_response.usage = Mock(total_tokens=10)
        
        with patch('src.azure_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_client.embeddings.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            client = AzureOpenAIClient(config=config)
            client.client = mock_client
            
            request = EmbeddingRequest(text="Apple Inc reported revenue of $394B")
            response = client.generate_embeddings(request)
            
            assert response.success is True
            assert response.embedding is not None
            assert response.dimensions == 1536
            assert response.token_usage == 10
    
    def test_generate_embeddings_no_deployment(self):
        """Test embeddings when deployment not configured."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345",
            embeddings_deployment=None  # Explicitly set to None
        )
        
        with patch('src.azure_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            client = AzureOpenAIClient(config=config)
            client.client = mock_client
            
            request = EmbeddingRequest(text="Test text")
            response = client.generate_embeddings(request)
            
            assert response.success is False
            assert response.error is not None
            # Should fail because embeddings deployment is not configured
            assert "deployment" in response.error.lower()


class TestErrorHandling:
    """Test error handling and retry logic."""
    
    def test_retry_catches_errors_gracefully(self):
        """Test retry logic catches errors and returns error response."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            # All attempts fail
            mock_client.responses.create.side_effect = Exception("Timeout")
            mock_openai_class.return_value = mock_client
            
            client = AzureOpenAIClient(config=config)
            client.client = mock_client
            
            request = LLMRequest(query="Test query")
            
            with patch('time.sleep'):  # Mock sleep to speed up test
                response = client.generate_sql(request)
            
            # Should return error response, not raise exception
            assert response.success is False
            assert "Timeout" in str(response.errors)
            # Error handling wraps the retry, so it returns error response
            # Circuit breaker should have been incremented
            assert client._circuit_breaker_failures > 0
    
    def test_error_handling_returns_error_response(self):
        """Test error handling returns proper error response."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_client.responses.create.side_effect = Exception("API Error")
            mock_openai_class.return_value = mock_client
            
            client = AzureOpenAIClient(config=config)
            client.client = mock_client
            
            request = LLMRequest(query="Test query")
            response = client.generate_sql(request)
            
            # Should return error response with details
            assert response.success is False
            assert len(response.errors) > 0
            assert "API Error" in str(response.errors)


class TestPydanticValidation:
    """Test Pydantic model validation."""
    
    def test_llm_request_validation(self):
        """Test LLMRequest validation."""
        # Valid request
        request = LLMRequest(query="Test query")
        assert request.query == "Test query"
        
        # Invalid request (empty query)
        with pytest.raises(ValueError):
            LLMRequest(query="")
    
    def test_llm_config_validation(self):
        """Test LLMConfig validation."""
        # Valid config
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        assert config.api_key == "test-key-12345"
        
        # Invalid config (placeholder API key)
        with pytest.raises(ValueError):
            LLMConfig(
                azure_endpoint="https://test.openai.azure.com/",
                api_key="your-api-key-here"
            )
    
    def test_llm_response_confidence_bounds(self):
        """Test LLMResponse confidence validation."""
        # Valid confidence
        response = LLMResponse(
            success=True,
            explanation="Test",
            confidence=0.95,
            processing_time_ms=100,
            model_version="gpt-5"
        )
        assert response.confidence == 0.95
        
        # Invalid confidence (out of bounds)
        with pytest.raises(ValueError):
            LLMResponse(
                success=True,
                explanation="Test",
                confidence=1.5,  # > 1.0
                processing_time_ms=100,
                model_version="gpt-5"
            )


class TestHelperMethods:
    """Test helper methods."""
    
    def test_extract_sql_from_code_block(self):
        """Test SQL extraction from code blocks."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI'):
            client = AzureOpenAIClient(config=config)
            
            content = "```sql\nSELECT * FROM companies;\n```"
            sql, explanation = client._extract_sql_and_explanation(content)
            
            assert sql is not None
            assert "SELECT" in sql.upper()
    
    def test_calculate_confidence(self):
        """Test confidence calculation."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI'):
            client = AzureOpenAIClient(config=config)
            
            # Good SQL query
            sql = "SELECT c.name FROM companies c JOIN num n ON c.cik = n.cik WHERE n.tag = 'Revenues';"
            explanation = "This query joins companies with financial data to retrieve revenue information."
            confidence = client._calculate_confidence(sql, explanation, "Show me revenue")
            
            assert confidence > 0.8
            
            # No SQL query
            confidence_no_sql = client._calculate_confidence(None, "No SQL", "test")
            assert confidence_no_sql < 0.6
    
    def test_extract_token_usage_with_reasoning(self):
        """Test token usage extraction with reasoning tokens."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI'):
            client = AzureOpenAIClient(config=config)
            
            # Mock response with reasoning tokens
            mock_response = Mock()
            mock_response.usage = Mock(
                input_tokens=100,
                output_tokens=200,
                total_tokens=300,
                output_tokens_details=Mock(reasoning_tokens=150)
            )
            
            token_usage = client._extract_token_usage(mock_response)
            
            assert token_usage['total_tokens'] == 300
            assert token_usage['reasoning_tokens'] == 150
            assert token_usage['reasoning_percentage'] == 75.0  # 150/200 * 100


class TestFactoryFunction:
    """Test factory function."""
    
    def test_get_azure_client(self):
        """Test get_azure_client factory function."""
        config = LLMConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key-12345"
        )
        
        with patch('src.azure_client.OpenAI'):
            client = get_azure_client(config=config)
            
            assert isinstance(client, AzureOpenAIClient)
            assert client.config == config


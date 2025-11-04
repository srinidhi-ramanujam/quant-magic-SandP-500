"""
SQL Generator - Generate SQL queries from extracted entities and templates.

Phase 0: Deterministic template matching (3 patterns)
Phase 1: Hybrid template selection (deterministic + LLM-assisted)
"""

from typing import Optional, List, Dict, Tuple
import json
import time
from src.models import (
    ExtractedEntities,
    IntelligenceMatch,
    GeneratedSQL,
    QueryTemplate,
    LLMTemplateSelectionRequest,
    LLMTemplateSelectionResponse,
)
from src.intelligence_loader import get_intelligence_loader
from src.telemetry import get_logger, RequestContext, log_component_timing
from src.config import get_config
from src.prompts import get_template_selection_prompt


class SQLGenerator:
    """Generate SQL queries using templates and extracted entities."""

    def __init__(self):
        """Initialize SQL generator with optional LLM template selection."""
        self.logger = get_logger()
        self.config = get_config()
        self.intelligence = get_intelligence_loader(use_phase_0_only=False)
        
        # Initialize Azure OpenAI client for template selection if enabled
        self.azure_client = None
        if self.config.template_selection_use_llm:
            try:
                from src.azure_client import AzureOpenAIClient
                self.azure_client = AzureOpenAIClient()
                self.logger.info("SQLGenerator initialized with LLM template selection")
            except Exception as e:
                self.logger.error(f"Failed to initialize Azure OpenAI client: {e}")
                self.logger.warning("Falling back to deterministic template selection only")
        else:
            self.logger.info("SQLGenerator initialized (deterministic template selection only)")

    def generate(
        self, entities: ExtractedEntities, question: str, context: RequestContext
    ) -> Optional[GeneratedSQL]:
        """
        Generate SQL query using hybrid template selection.
        
        Hybrid approach:
        - High confidence (≥0.8): Fast path, use template directly
        - Medium confidence (0.5-0.8): LLM confirmation/selection
        - Low confidence (<0.5): LLM selects from all templates or recommends custom SQL

        Args:
            entities: Extracted entities from question
            question: Original natural language question
            context: Request context for telemetry

        Returns:
            GeneratedSQL if successful, None if custom SQL needed or unable to generate
        """
        with log_component_timing(context, "sql_generation"):
            # Step 1: Deterministic matching
            intelligence_match = self.intelligence.match_pattern(question)
            
            # Step 2: Decision logic based on LLM availability and confidence
            if not self.azure_client or not self.config.template_selection_use_llm:
                # LLM disabled or unavailable - use deterministic only
                if intelligence_match.template:
                    context.add_metadata("template_selection_method", "deterministic_only")
                    return self._generate_from_template(intelligence_match, entities)
                else:
                    self.logger.warning("No template matched, LLM disabled")
                    return None
            
            # Step 3: Hybrid logic with LLM
            if intelligence_match.match_confidence >= self.config.template_selection_fast_path_threshold:
                # HIGH CONFIDENCE: Fast path, skip LLM
                self.logger.info(
                    f"Fast path (confidence={intelligence_match.match_confidence:.2f}): "
                    f"template={intelligence_match.template.template_id if intelligence_match.template else 'None'}"
                )
                context.add_metadata("template_selection_method", "fast_path")
                
                if intelligence_match.template:
                    return self._generate_from_template(intelligence_match, entities)
                else:
                    return None
            
            elif intelligence_match.match_confidence >= self.config.template_selection_llm_threshold:
                # MEDIUM CONFIDENCE: LLM confirmation with single candidate
                self.logger.info(
                    f"LLM confirmation path (confidence={intelligence_match.match_confidence:.2f})"
                )
                context.add_metadata("template_selection_method", "llm_confirmation")
                candidates = [intelligence_match.template] if intelligence_match.template else []
                
            else:
                # LOW CONFIDENCE: LLM selection from all templates
                self.logger.info(
                    f"LLM fallback path (confidence={intelligence_match.match_confidence:.2f})"
                )
                context.add_metadata("template_selection_method", "llm_fallback")
                candidates = self.intelligence.get_all_templates()
            
            # Step 4: Call LLM for template selection
            result = self._select_template_with_llm(question, entities, candidates, context)
            
            if result is None:
                # LLM recommends custom SQL generation
                self.logger.info("LLM recommends custom SQL generation")
                context.add_metadata("llm_recommendation", "custom_sql")
                return None
            
            template, parameter_mapping = result
            
            # Step 5: Generate SQL from LLM-selected template
            return self._generate_from_template_with_params(template, parameter_mapping, entities)

    def _generate_from_template(
        self, intelligence_match: IntelligenceMatch, entities: ExtractedEntities
    ) -> Optional[GeneratedSQL]:
        """
        Generate SQL by populating a template.

        Args:
            intelligence_match: Matched template
            entities: Extracted entities

        Returns:
            GeneratedSQL with populated SQL query
        """
        template = intelligence_match.template
        params = intelligence_match.matched_parameters.copy()

        self.logger.debug(f"Generating SQL from template: {template.template_id}")
        self.logger.debug(f"Template parameters: {params}")

        # Validate we have all required parameters
        missing_params = set(template.parameters) - set(params.keys())
        if missing_params:
            self.logger.warning(f"Missing parameters for template: {missing_params}")

            # Try to fill missing parameters from entities
            params = self._fill_missing_parameters(params, entities, template)

            # Check again
            missing_params = set(template.parameters) - set(params.keys())
            if missing_params:
                self.logger.error(f"Still missing parameters: {missing_params}")
                return None

        # Populate template with parameters
        try:
            sql = template.sql_template
            for param_name, param_value in params.items():
                placeholder = f"{{{param_name}}}"
                if placeholder in sql:
                    sql = sql.replace(placeholder, param_value)

            self.logger.info(f"Generated SQL: {sql[:100]}...")

            return GeneratedSQL(
                sql=sql,
                parameters=params,
                template_id=template.template_id,
                generation_method="template",
                confidence=intelligence_match.match_confidence,
            )

        except Exception as e:
            self.logger.error(f"Failed to generate SQL: {e}")
            return None

    def _fill_missing_parameters(
        self, params: dict, entities: ExtractedEntities, template
    ) -> dict:
        """
        Try to fill missing parameters from extracted entities.

        Args:
            params: Current parameters
            entities: Extracted entities
            template: Query template

        Returns:
            Updated parameters dictionary
        """
        # Generic parameter mapping from entities
        # Map parameter names to entity attributes
        entity_mappings = {
            "company": entities.companies,
            "sector": entities.sectors,
            "metric": entities.metrics,
            "time_period": entities.time_periods,
            "cik": entities.companies,  # CIK can sometimes be extracted as company
        }
        
        # Try to fill each missing parameter
        for param_name in template.parameters:
            if param_name not in params:
                # Check if we have an entity that matches this parameter
                if param_name in entity_mappings and entity_mappings[param_name]:
                    params[param_name] = entity_mappings[param_name][0]
                    self.logger.debug(
                        f"Filled '{param_name}' parameter from entities: {entity_mappings[param_name][0]}"
                    )
        
        # Special handling for specific parameter types
        # State/jurisdiction normalization
        if "state" in template.parameters and "state" not in params:
            # Try to extract state from question
            from src.entity_extractor import get_entity_extractor
            extractor = get_entity_extractor()
            # Look for state names in sectors (sometimes misclassified)
            for potential_state in entities.sectors + entities.companies:
                normalized = extractor._normalize_state_code(potential_state)
                if normalized:
                    params["state"] = normalized
                    self.logger.debug(f"Filled 'state' parameter: {normalized}")
                    break
        
        if "jurisdiction" in template.parameters and "jurisdiction" not in params:
            # Similar to state
            from src.entity_extractor import get_entity_extractor
            extractor = get_entity_extractor()
            for potential_jurisdiction in entities.sectors + entities.companies:
                normalized = extractor._normalize_state_code(potential_jurisdiction)
                if normalized:
                    params["jurisdiction"] = normalized
                    self.logger.debug(f"Filled 'jurisdiction' parameter: {normalized}")
                    break

        return params

    def _select_template_with_llm(
        self,
        question: str,
        entities: ExtractedEntities,
        candidate_templates: List[QueryTemplate],
        context: RequestContext
    ) -> Optional[Tuple[QueryTemplate, Dict[str, str]]]:
        """
        Use LLM to select best template from candidates or recommend custom SQL.
        
        Args:
            question: User's natural language question
            entities: Extracted entities from Stage 1
            candidate_templates: List of candidate templates (can be empty)
            context: Request context for telemetry
            
        Returns:
            Tuple of (selected_template, parameter_mapping) or None if custom SQL needed
        """
        # Format entities for prompt
        entities_dict = {
            "companies": entities.companies,
            "metrics": entities.metrics,
            "sectors": entities.sectors,
            "time_periods": entities.time_periods,
            "question_type": entities.question_type
        }
        
        # Format candidate templates for prompt
        candidate_dicts = [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "sql_template": t.sql_template
            }
            for t in candidate_templates
        ]
        
        # Generate prompt
        prompt = get_template_selection_prompt(question, entities_dict, candidate_dicts)
        
        # Call LLM with retry logic
        max_retries = self.config.template_selection_max_retries
        last_error = None
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"LLM template selection attempt {attempt + 1}/{max_retries}")
                
                start_time = time.time()
                
                # Check Azure client availability
                if not self.azure_client or not self.azure_client.is_available():
                    raise ValueError("Azure OpenAI client not available")
                
                # Prepare API call parameters based on model
                model_name = self.azure_client.config.deployment_name or ""
                requires_special_params = any(x in model_name.lower() for x in ["o1", "gpt-5"])
                
                if requires_special_params:
                    # gpt-5 and o1 models require special parameters
                    response = self.azure_client.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        max_completion_tokens=500,
                    )
                else:
                    # Standard models
                    response = self.azure_client.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "You are a SQL template selection assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=self.config.template_selection_temperature,
                        max_completion_tokens=500,
                    )
                
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                # Extract content from response
                content = response.choices[0].message.content
                
                # Parse JSON response
                llm_output = self._parse_llm_response(content)
                
                # Extract token usage
                token_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                }
                
                # Parse into LLMTemplateSelectionResponse
                llm_response = LLMTemplateSelectionResponse(**llm_output)
                
                # Track telemetry
                if not context.metadata.get("llm_calls"):
                    context.metadata["llm_calls"] = []
                context.metadata["llm_calls"].append({
                    "stage": "template_selection",
                    "tokens": token_usage,
                    "latency_ms": elapsed_ms,
                    "success": True,
                    "confidence": llm_response.confidence
                })
                
                self.logger.info(
                    f"LLM template selection: template_id={llm_response.selected_template_id}, "
                    f"confidence={llm_response.confidence:.2f}, use_custom_sql={llm_response.use_custom_sql}, "
                    f"tokens={sum(token_usage.values())}, latency={elapsed_ms}ms"
                )
                
                # Handle response
                if llm_response.use_custom_sql or llm_response.selected_template_id is None:
                    # LLM recommends custom SQL
                    self.logger.info(f"LLM recommends custom SQL: {llm_response.reasoning}")
                    return None
                
                # Get selected template
                template = self.intelligence.get_template_by_id(llm_response.selected_template_id)
                
                if template is None:
                    self.logger.error(
                        f"LLM selected invalid template_id: {llm_response.selected_template_id}"
                    )
                    # Try fallback to deterministic if available
                    if candidate_templates and len(candidate_templates) > 0:
                        self.logger.warning("Falling back to first candidate template")
                        template = candidate_templates[0]
                        return (template, llm_response.parameter_mapping)
                    return None
                
                return (template, llm_response.parameter_mapping)
                
            except json.JSONDecodeError as e:
                last_error = f"JSON parsing error: {e}"
                self.logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                continue
                
            except Exception as e:
                last_error = f"LLM template selection error: {e}"
                self.logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                continue
        
        # All attempts failed
        self.logger.error(
            f"LLM template selection failed after {max_retries} attempts: {last_error}"
        )
        
        # Fallback to deterministic if available
        if candidate_templates and len(candidate_templates) > 0:
            self.logger.warning("Falling back to first candidate template")
            return (candidate_templates[0], {})
        
        return None

    def _parse_llm_response(self, content: str) -> dict:
        """
        Parse JSON from LLM response, handling markdown code blocks.
        
        Args:
            content: Raw LLM response content
            
        Returns:
            Parsed dictionary
            
        Raises:
            json.JSONDecodeError: If unable to parse JSON
        """
        # Try direct JSON parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try extracting from markdown code block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()
                return json.loads(json_str)
        
        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()
                return json.loads(json_str)
        
        # Last resort: try to find JSON object in content
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        # Unable to parse
        raise json.JSONDecodeError("Unable to extract JSON from LLM response", content, 0)

    def _generate_from_template_with_params(
        self,
        template: QueryTemplate,
        parameter_mapping: Dict[str, str],
        entities: ExtractedEntities
    ) -> Optional[GeneratedSQL]:
        """
        Generate SQL using LLM-provided parameter mapping.
        
        Falls back to entity-based parameter filling if mapping incomplete.
        
        Args:
            template: Selected query template
            parameter_mapping: Parameter values from LLM
            entities: Extracted entities for fallback parameter filling
            
        Returns:
            GeneratedSQL if successful, None if unable to generate
        """
        params = parameter_mapping.copy()
        
        self.logger.debug(
            f"Generating SQL from template: {template.template_id} with LLM parameters: {params}"
        )
        
        # Check for missing parameters
        missing_params = set(template.parameters) - set(params.keys())
        if missing_params:
            self.logger.warning(
                f"LLM parameter mapping incomplete, missing: {missing_params}"
            )
            # Try to fill from entities
            params = self._fill_missing_parameters(params, entities, template)
            
            # Check again
            missing_params = set(template.parameters) - set(params.keys())
            if missing_params:
                self.logger.error(f"Still missing parameters after fallback: {missing_params}")
                return None
        
        # Populate template with parameters
        try:
            sql = template.sql_template
            for param_name, param_value in params.items():
                placeholder = f"{{{param_name}}}"
                if placeholder in sql:
                    sql = sql.replace(placeholder, param_value)
            
            self.logger.info(f"Generated SQL from LLM-selected template: {sql[:100]}...")
            
            return GeneratedSQL(
                sql=sql,
                parameters=params,
                template_id=template.template_id,
                generation_method="llm_template_selection",
                confidence=0.85,  # High confidence for LLM-selected templates
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate SQL from LLM template: {e}")
            return None

    def validate_sql(self, sql: str) -> bool:
        """
        Basic SQL validation.

        Args:
            sql: SQL query string

        Returns:
            True if valid, False otherwise
        """
        # Basic checks
        if not sql or not sql.strip():
            return False

        sql_upper = sql.upper().strip()

        # Must start with SELECT
        if not sql_upper.startswith("SELECT"):
            return False

        # Must contain FROM
        if "FROM" not in sql_upper:
            return False

        # Should not contain dangerous keywords (for read-only safety)
        dangerous = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "ALTER",
            "CREATE",
            "TRUNCATE",
        ]
        for keyword in dangerous:
            if keyword in sql_upper:
                self.logger.error(f"SQL contains dangerous keyword: {keyword}")
                return False

        return True


# Global instance
_generator: Optional[SQLGenerator] = None


def get_sql_generator() -> SQLGenerator:
    """Get the global SQL generator instance."""
    global _generator
    if _generator is None:
        _generator = SQLGenerator()
    return _generator

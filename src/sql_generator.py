"""
SQL Generator - Generate SQL queries from extracted entities and templates.

Phase 0: Deterministic template matching (3 patterns)
Phase 1: Hybrid template selection (deterministic + LLM-assisted)
"""

import re
from typing import Optional, List, Dict, Tuple, Any
import json
import time
from datetime import datetime
from src.models import (
    ExtractedEntities,
    IntelligenceMatch,
    GeneratedSQL,
    QueryTemplate,
    LLMRequest,
    LLMTemplateSelectionRequest,
    LLMTemplateSelectionResponse,
)
from src.intelligence_loader import get_intelligence_loader
from src.telemetry import get_logger, RequestContext, log_component_timing
from src.config import get_config
from src.prompts import get_template_selection_prompt
from src import schema_docs
from src.sql_validator import SQLValidator
from src.entity_extractor import normalize_company_name
from src.query_engine import quick_query
from src.query_engine import QueryEngine
from src.hybrid_retrieval import TemplateIntentRetriever
from src.llm_guard import LLMAvailabilityError


class SQLGenerator:
    """Generate SQL queries using templates and extracted entities."""

    def __init__(self, use_llm: bool = True):
        """Initialize SQL generator with optional LLM template selection."""
        self.logger = get_logger()
        self.config = get_config()
        self.intelligence = get_intelligence_loader(use_phase_0_only=False)
        self.use_llm = bool(use_llm)
        self._company_lookup_cache: Dict[str, str] = {}
        self._company_name_index: Optional[Dict[str, str]] = None
        self._company_token_index: Optional[Dict[str, List[str]]] = None

        # Initialize Azure OpenAI client for template selection if enabled
        self.azure_client = None
        if self.use_llm:
            try:
                from src.azure_client import AzureOpenAIClient

                client = AzureOpenAIClient()
            except Exception as exc:
                raise LLMAvailabilityError(
                    f"SQLGenerator: failed to initialize Azure OpenAI client ({exc})"
                ) from exc

            if not client.is_available():
                raise LLMAvailabilityError(
                    "SQLGenerator: Azure OpenAI client is not available."
                )

            self.azure_client = client
            self.logger.info("SQLGenerator initialized with LLM template selection")
        else:
            self.logger.info(
                "SQLGenerator initialized (deterministic template selection only)"
            )

        self.template_retriever = TemplateIntentRetriever.create_default()
        if self.template_retriever:
            self.logger.info("Template intent retriever enabled")

        self.validator = SQLValidator(use_llm=self.use_llm)

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
            use_llm_available = bool(self.azure_client) and self.use_llm

            if (
                intelligence_match.template is None
                and self.template_retriever is not None
            ):
                recovered = self._retrieve_template_with_embeddings(
                    question, entities, context
                )
                if recovered:
                    intelligence_match = recovered
                    context.add_metadata(
                        "template_selection_method", "embedding_retriever"
                    )

            # Step 2: If LLM path unavailable, stay deterministic
            if not use_llm_available:
                if intelligence_match.template:
                    context.add_metadata(
                        "template_selection_method",
                        context.metadata.get(
                            "template_selection_method", "deterministic_only"
                        ),
                    )
                    return self._generate_from_template(intelligence_match, entities)

                self.logger.warning("No template matched and LLM unavailable")
                return None

            # Step 3: Hybrid logic with LLM
            confidence = intelligence_match.match_confidence
            fast_threshold = self.config.template_selection_fast_path_threshold
            llm_threshold = self.config.template_selection_llm_threshold

            if confidence >= fast_threshold and intelligence_match.template is not None:
                # HIGH CONFIDENCE: Fast path, skip LLM
                self.logger.info(
                    "Fast path (confidence=%.2f): template=%s",
                    confidence,
                    intelligence_match.template.template_id,
                )
                context.add_metadata("template_selection_method", "fast_path")
                return self._generate_from_template(intelligence_match, entities)

            if confidence >= llm_threshold and intelligence_match.template is not None:
                # MEDIUM CONFIDENCE: Ask LLM to confirm chosen template
                self.logger.info("LLM confirmation path (confidence=%.2f)", confidence)
                context.add_metadata("template_selection_method", "llm_confirmation")
                candidates: List[QueryTemplate] = [intelligence_match.template]
            else:
                # LOW CONFIDENCE: Provide full template catalog to LLM
                self.logger.info("LLM fallback path (confidence=%.2f)", confidence)
                context.add_metadata("template_selection_method", "llm_fallback")
                candidates = self.intelligence.get_all_templates()

            # Step 4: Call LLM for template selection or custom SQL recommendation
            result = self._select_template_with_llm(
                question, entities, candidates, context
            )

            if result is None:
                self.logger.info("LLM recommends custom SQL generation")
                context.add_metadata("llm_recommendation", "custom_sql")
                custom_sql = self._generate_custom_sql(entities, question, context)
                if custom_sql:
                    return custom_sql
                return None

            template, parameter_mapping = result

            # Step 5: Generate SQL from LLM-selected template
            return self._generate_from_template_with_params(
                template, parameter_mapping, entities
            )

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
            self.logger.debug(
                "Missing parameters for template %s: %s",
                template.template_id,
                missing_params,
            )

            # Try to fill missing parameters from entities
            params = self._fill_missing_parameters(params, entities, template)

            # Check again
            missing_params = set(template.parameters) - set(params.keys())
            if missing_params:
                params = self._apply_default_parameters(
                    params, missing_params, template
                )
                missing_params = set(template.parameters) - set(params.keys())
                if missing_params:
                    self.logger.error(f"Still missing parameters: {missing_params}")
                    return None

        params = self._apply_entity_overrides(params, entities, template)

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

    def _apply_entity_overrides(
        self,
        params: Dict[str, str],
        entities: ExtractedEntities,
        template: QueryTemplate,
    ) -> Dict[str, str]:
        """
        Use extracted entities to normalize or override populated parameters.

        Ensures canonical values (e.g., company names) flow into the SQL template.
        """
        if not template.parameters or entities is None:
            return params

        updated = params.copy()

        if "company" in template.parameters and entities.companies:
            raw_company = next((c for c in entities.companies if c), "")
            canonical_company = normalize_company_name(raw_company)
            if canonical_company:
                canonical_company = self._canonicalize_company_from_dataset(
                    canonical_company
                )
                current_company = updated.get("company", "")
                current_normalized = (
                    normalize_company_name(current_company) if current_company else ""
                )
                if not current_company or canonical_company != current_normalized:
                    updated["company"] = canonical_company

        if "sector" in template.parameters and entities.sectors:
            canonical_sector = next((s for s in entities.sectors if s), "")
            if canonical_sector:
                current_sector = updated.get("sector", "")
                if (
                    not current_sector
                    or canonical_sector.lower() not in current_sector.lower()
                ):
                    updated["sector"] = canonical_sector
        if "sector" in template.parameters:
            sector_value = updated.get("sector")
            if sector_value:
                cleaned = sector_value.strip().lower()
                if (
                    cleaned in {"all", "all sector", "all sectors"}
                    or "all sector" in cleaned
                    or "which" in cleaned
                    or "what" in cleaned
                ):
                    updated["sector"] = "ALL"

        if "metric" in template.parameters and entities.metrics:
            canonical_metric = next((m for m in entities.metrics if m), "")
            if canonical_metric:
                updated["metric"] = canonical_metric

        if "time_period" in template.parameters and entities.time_periods:
            canonical_period = next((t for t in entities.time_periods if t), "")
            if canonical_period:
                current_period = updated.get("time_period", "")
                if (
                    not current_period
                    or canonical_period.lower() not in current_period.lower()
                ):
                    updated["time_period"] = canonical_period

        return updated

    def _apply_default_parameters(
        self, params: Dict[str, str], missing_params: set, template: QueryTemplate
    ) -> Dict[str, str]:
        """Provide fallback values for optional template parameters."""
        defaults: Dict[str, str] = {}

        if "sector" in missing_params:
            defaults["sector"] = "ALL"

        if "start_year" in missing_params or "end_year" in missing_params:
            current_year = datetime.utcnow().year
            default_end = max(2015, current_year - 2)
            default_start = default_end - 2
            if "start_year" in missing_params:
                defaults["start_year"] = str(default_start)
            if "end_year" in missing_params:
                defaults["end_year"] = str(default_end)

        if "min_revenue" in missing_params:
            defaults["min_revenue"] = "5000000000"

        if "company_values" in missing_params:
            defaults[
                "company_values"
            ] = "('WALMART INC.'),('TARGET CORP'),('HOME DEPOT, INC.'),('AMAZON COM INC'),('COSTCO WHOLESALE CORP /NEW'),('BEST BUY CO INC')"

        if "quarter_count" in missing_params:
            defaults["quarter_count"] = "6"

        if "min_period" in missing_params:
            defaults["min_period"] = "2022-01-01"

        if "limit" in missing_params:
            defaults["limit"] = "10"

        if "rank" in missing_params:
            defaults["rank"] = "1"

        if "min_growth_pct" in missing_params:
            defaults["min_growth_pct"] = "0"

        if not defaults:
            return params

        self.logger.debug(
            "Applying default parameters for %s: %s",
            template.template_id,
            defaults,
        )

        updated = params.copy()
        updated.update(defaults)
        return updated

    @staticmethod
    def _standardize_company_key(value: str) -> str:
        """Generate a normalized key for comparing company names."""
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    @staticmethod
    def _first_token(value: str) -> str:
        """Return the first alphanumeric token for a company name."""
        tokens = re.findall(r"[A-Z0-9]+", value.upper())
        return tokens[0] if tokens else ""

    def _ensure_company_indexes(self) -> None:
        """Load company name indexes from the dataset if not already populated."""
        if self._company_name_index is not None:
            return

        try:
            df = quick_query(
                "SELECT DISTINCT name FROM companies WHERE name IS NOT NULL"
            )
            names = df["name"].astype(str).tolist()
            name_index: Dict[str, str] = {}
            token_index: Dict[str, List[str]] = {}

            for name in names:
                standardized = self._standardize_company_key(name)
                if standardized and standardized not in name_index:
                    name_index[standardized] = name

                first_token = self._first_token(name)
                if first_token:
                    token_index.setdefault(first_token, []).append(name)

            # Prefer shortest name for token collisions to reduce noise
            token_index = {
                token: sorted(options, key=len)
                for token, options in token_index.items()
            }

            self._company_name_index = name_index
            self._company_token_index = token_index
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Unable to load company name index: %s", exc)
            self._company_name_index = {}
            self._company_token_index = {}

    def _canonicalize_company_from_dataset(self, company: str) -> str:
        """Snap company value to the canonical spelling used in the companies table."""
        cached = self._company_lookup_cache.get(company)
        if cached:
            return cached

        self._ensure_company_indexes()

        resolved = company
        if self._company_name_index:
            key = self._standardize_company_key(company)
            if key in self._company_name_index:
                resolved = self._company_name_index[key]
            else:
                token = self._first_token(company)
                candidates = []
                if self._company_token_index and token:
                    candidates = self._company_token_index.get(token, [])

                if candidates:
                    resolved = candidates[0]

        self._company_lookup_cache[company] = resolved
        return resolved

    def _select_template_with_llm(
        self,
        question: str,
        entities: ExtractedEntities,
        candidate_templates: List[QueryTemplate],
        context: RequestContext,
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
            "question_type": entities.question_type,
        }

        # Format candidate templates for prompt
        candidate_dicts = [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "sql_template": t.sql_template,
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
                self.logger.debug(
                    f"LLM template selection attempt {attempt + 1}/{max_retries}"
                )

                start_time = time.time()

                # Check Azure client availability
                if not self.azure_client or not self.azure_client.is_available():
                    raise ValueError("Azure OpenAI client not available")

                # Prepare API call parameters based on model
                model_name = self.azure_client.config.deployment_name or ""
                requires_special_params = any(
                    x in model_name.lower() for x in ["o1", "gpt-5"]
                )

                if requires_special_params:
                    # gpt-5 and o1 models require special parameters
                    response = self.azure_client.client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_completion_tokens=500,
                    )
                else:
                    # Standard models
                    response = self.azure_client.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a SQL template selection assistant.",
                            },
                            {"role": "user", "content": prompt},
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
                    "completion_tokens": response.usage.completion_tokens,
                }

                # Parse into LLMTemplateSelectionResponse
                llm_response = LLMTemplateSelectionResponse(**llm_output)

                # Track telemetry
                if not context.metadata.get("llm_calls"):
                    context.metadata["llm_calls"] = []
                context.metadata["llm_calls"].append(
                    {
                        "stage": "template_selection",
                        "tokens": token_usage,
                        "latency_ms": elapsed_ms,
                        "success": True,
                        "confidence": llm_response.confidence,
                    }
                )

                self.logger.info(
                    f"LLM template selection: template_id={llm_response.selected_template_id}, "
                    f"confidence={llm_response.confidence:.2f}, use_custom_sql={llm_response.use_custom_sql}, "
                    f"tokens={sum(token_usage.values())}, latency={elapsed_ms}ms"
                )

                # Handle response
                if (
                    llm_response.use_custom_sql
                    or llm_response.selected_template_id is None
                ):
                    # LLM recommends custom SQL
                    self.logger.info(
                        f"LLM recommends custom SQL: {llm_response.reasoning}"
                    )
                    return None

                # Get selected template
                template = self.intelligence.get_template_by_id(
                    llm_response.selected_template_id
                )

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
        raise LLMAvailabilityError(
            f"LLM template selection failed after {max_retries} attempts: {last_error}"
        )

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

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        # Unable to parse
        raise json.JSONDecodeError(
            "Unable to extract JSON from LLM response", content, 0
        )

    def _generate_from_template_with_params(
        self,
        template: QueryTemplate,
        parameter_mapping: Dict[str, str],
        entities: ExtractedEntities,
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
                self.logger.error(
                    f"Still missing parameters after fallback: {missing_params}"
                )
                return None

        params = self._apply_entity_overrides(params, entities, template)

        # Populate template with parameters
        try:
            sql = template.sql_template
            for param_name, param_value in params.items():
                placeholder = f"{{{param_name}}}"
                if placeholder in sql:
                    sql = sql.replace(placeholder, param_value)

            self.logger.info(
                f"Generated SQL from LLM-selected template: {sql[:100]}..."
            )

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

    def _generate_custom_sql(
        self,
        entities: ExtractedEntities,
        question: str,
        context: RequestContext,
    ) -> Optional[GeneratedSQL]:
        """Fallback path that asks the LLM to write SQL from scratch."""

        if not self.azure_client or not self.use_llm:
            self.logger.debug("Custom SQL generation skipped (LLM unavailable)")
            return None

        try:
            entity_payload = entities.model_dump()
            domain_hints = self._build_domain_hints(question, entities)
            request_context = {
                "entities": entity_payload,
                "schema": schema_docs.schema_for_prompt(),
            }
            if domain_hints:
                request_context["domain_hints"] = domain_hints

            llm_request = LLMRequest(
                query=question,
                context=request_context,
                similar_queries=context.metadata.get("similar_queries", []),
                template_attempts=context.metadata.get("template_attempts", []),
            )

            response = self.azure_client.generate_sql(llm_request)

            attempt_record = {
                "sql": response.generated_sql,
                "confidence": response.confidence,
                "token_usage": response.token_usage,
                "latency_ms": response.processing_time_ms,
            }

            if not response.success or not response.generated_sql:
                attempt_record["success"] = False
                attempt_record["failure_reason"] = (
                    response.explanation or "LLM response missing SQL"
                )
                context.metadata.setdefault("custom_sql_attempts", []).append(
                    attempt_record
                )
                self.logger.warning(
                    "Custom SQL generation failed: %s", response.explanation
                )
                return None

            validation_ok, validation_reason, validation_confidence = (
                self.validator.validate(
                    response.generated_sql,
                    question,
                    entities.model_dump(),
                    context,
                )
            )

            attempt_record["success"] = response.success and validation_ok
            attempt_record["validation_confidence"] = validation_confidence
            if validation_reason:
                attempt_record["failure_reason"] = validation_reason

            context.metadata.setdefault("custom_sql_attempts", []).append(
                attempt_record
            )

            if not validation_ok:
                self.logger.warning(
                    "Generated SQL failed validation checks: %s", validation_reason
                )
                return None

            llm_calls = context.metadata.setdefault("llm_calls", [])
            llm_calls.append(
                {
                    "stage": "custom_sql",
                    "tokens": response.token_usage,
                    "latency_ms": response.processing_time_ms,
                    "success": response.success,
                }
            )

            return GeneratedSQL(
                sql=response.generated_sql,
                parameters={},
                template_id=None,
                generation_method="llm_custom",
                confidence=response.confidence,
            )

        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"Unexpected error generating custom SQL: {exc}")
            return None

    def _retrieve_template_with_embeddings(
        self,
        question: str,
        entities: ExtractedEntities,
        context: RequestContext,
    ) -> Optional[IntelligenceMatch]:
        if not self.template_retriever:
            return None

        result = self.template_retriever.retrieve(question)
        if not result:
            return None

        template = self.intelligence.get_template_by_id(result.template_id)
        if not template:
            return None

        matched_params = self.intelligence.extract_parameters_for_template(
            question, template
        )
        context.add_metadata("template_retriever_score", f"{result.score:.3f}")

        return IntelligenceMatch(
            template=template,
            match_confidence=result.score,
            matched_parameters=matched_params,
            fallback_to_llm=False,
        )

    def validate_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Basic SQL validation.

        Args:
            sql: SQL query string

        Returns:
            Tuple of (is_valid, failure_reason)
        """
        return self.validator.validate_static(sql)

    def _build_domain_hints(
        self, question: str, entities: ExtractedEntities
    ) -> Dict[str, Any]:
        """Derive lightweight domain hints to steer custom SQL generation."""

        hints: Dict[str, Any] = {}
        question_lower = question.lower()

        if entities.metrics:
            hints["metrics"] = entities.metrics
            tag_map: Dict[str, List[str]] = {}
            for metric in entities.metrics:
                tags = schema_docs.COMMON_METRIC_TAGS.get(metric.lower())
                if tags:
                    tag_map[metric] = tags
            if tag_map:
                hints["metric_tags"] = tag_map

        if entities.companies:
            hints["companies"] = entities.companies

        if entities.sectors:
            hints["sectors"] = entities.sectors

        if entities.time_periods:
            hints["time_periods"] = entities.time_periods

        if entities.question_type:
            hints["question_type"] = entities.question_type

        threshold = self._extract_threshold_hint(question_lower)
        if threshold:
            hints["threshold"] = threshold

        ordering = self._extract_ordering_hint(question_lower)
        if ordering:
            hints["ordering"] = ordering

        currency_match = re.search(
            r"\b(usd|cad|eur|gbp|jpy|cny|aud|mxn|chf)\b", question_lower
        )
        if currency_match:
            hints["currency_filter"] = (
                f"Filter num.uom for '{currency_match.group(1).upper()}'"
            )

        if "per share" in question_lower or "per-share" in question_lower:
            hints["unit_context"] = (
                "Question references per-share metrics; consider num.uom = 'shares'."
            )

        if "segment" in question_lower or "by segment" in question_lower:
            hints["segment_context"] = (
                "Segment-level data may be required; avoid filtering num.segments to NULL if segments requested."
            )

        return hints

    @staticmethod
    def _extract_threshold_hint(question_lower: str) -> Optional[str]:
        """Detect numeric thresholds in the question for prompt guidance."""
        match = re.search(
            r"(over|above|greater than|at least|exceeding|more than)\s+\$?([\d,.,]+)\s*(trillion|billion|million|thousand|bn|m|k|percent|%)?",
            question_lower,
        )
        if not match:
            return None

        comparator = match.group(1)
        value = match.group(2)
        scale = match.group(3) or ""
        normalized_scale = scale.lower()
        if normalized_scale in {"bn"}:
            normalized_scale = "billion"
        elif normalized_scale in {"m"}:
            normalized_scale = "million"
        elif normalized_scale in {"k"}:
            normalized_scale = "thousand"

        return f"{comparator} {value} {normalized_scale}".strip()

    @staticmethod
    def _extract_ordering_hint(question_lower: str) -> Optional[str]:
        """Detect ordering intent (e.g., top/bottom results)."""
        if any(
            keyword in question_lower
            for keyword in ["top", "largest", "highest", "biggest", "most"]
        ):
            return "Use ORDER BY metric DESC with LIMIT to surface top results."
        if any(
            keyword in question_lower
            for keyword in ["smallest", "lowest", "least", "bottom"]
        ):
            return "Use ORDER BY metric ASC with LIMIT to surface bottom results."
        return None


# Global instance
_generator: Optional[SQLGenerator] = None


def get_sql_generator(force_refresh: bool = False) -> SQLGenerator:
    """Get the global SQL generator instance."""
    global _generator
    if _generator is None or force_refresh:
        _generator = SQLGenerator()
    return _generator

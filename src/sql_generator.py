"""
SQL Generator - Generate SQL queries from extracted entities and templates.

For Phase 0, supports 3 template patterns:
1. Sector count
2. Company CIK lookup
3. Company sector lookup
"""

from typing import Optional
from src.models import ExtractedEntities, IntelligenceMatch, GeneratedSQL
from src.intelligence_loader import get_intelligence_loader
from src.telemetry import get_logger, RequestContext, log_component_timing


class SQLGenerator:
    """Generate SQL queries using templates and extracted entities."""

    def __init__(self):
        """Initialize SQL generator."""
        self.logger = get_logger()
        self.intelligence = get_intelligence_loader(use_phase_0_only=True)
        self.logger.info("SQLGenerator initialized with Phase 0 templates")

    def generate(
        self, entities: ExtractedEntities, question: str, context: RequestContext
    ) -> Optional[GeneratedSQL]:
        """
        Generate SQL query from entities.

        Args:
            entities: Extracted entities from question
            question: Original natural language question
            context: Request context for telemetry

        Returns:
            GeneratedSQL if successful, None if unable to generate
        """
        with log_component_timing(context, "sql_generation"):
            # First, try to match to a template
            intelligence_match = self.intelligence.match_pattern(question)

            if intelligence_match.template:
                return self._generate_from_template(intelligence_match, entities)
            else:
                self.logger.warning(
                    "No template matched, cannot generate SQL in Phase 0"
                )
                return None

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
        # Check template ID to know what we need
        if template.template_id == "sector_count" and "sector" not in params:
            if entities.sectors:
                params["sector"] = entities.sectors[0]
                self.logger.debug(
                    f"Filled 'sector' parameter from entities: {entities.sectors[0]}"
                )

        elif (
            template.template_id in ["company_cik", "company_sector"]
            and "company" not in params
        ):
            if entities.companies:
                params["company"] = entities.companies[0]
                self.logger.debug(
                    f"Filled 'company' parameter from entities: {entities.companies[0]}"
                )

        return params

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

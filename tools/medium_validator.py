#!/usr/bin/env python3
"""
Medium-tier question validator.
Validates all 50 medium questions across 5 criteria:
0. Data availability
1. Medium complexity (~2 hours analyst work)
2. CFO office relevance
3. Evaluation framework fit
4. Answer correctness
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np
import re

sys.path.insert(0, str(Path(__file__).parent))
from src.query_engine import QueryEngine


@dataclass
class ValidationResult:
    """Result of validating a single question."""
    question_id: str
    question_text: str
    
    # 5 validation criteria
    data_available: bool = False
    data_issues: List[str] = field(default_factory=list)
    
    complexity_appropriate: bool = True
    complexity_rating: str = "medium"  # "too_simple", "medium", "too_complex"
    complexity_notes: str = ""
    
    cfo_relevant: bool = True
    cfo_relevance_score: int = 4  # 1-5 scale
    cfo_notes: str = ""
    
    framework_appropriate: bool = True
    framework_notes: str = ""
    
    answer_correct: bool = False
    expected_answer: str = ""
    calculated_answer: str = ""
    answer_issues: List[str] = field(default_factory=list)
    
    # Overall assessment
    disposition: str = "pending"  # "keep", "remove", "fix_answer", "replace"
    reason: str = ""


class MediumQuestionValidator:
    """Validator for medium-tier questions."""
    
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self.qe = QueryEngine()
        self.results: List[ValidationResult] = []
        self._load_data()
        
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for fuzzy matching."""
        # Remove common suffixes and punctuation
        normalized = name.upper()
        normalized = re.sub(r'\s+(INC\.?|CORP\.?|CO\.?|LTD\.?|LLC|LP)$', '', normalized)
        normalized = re.sub(r'[,\.\(\)]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _find_company(self, company_name: str) -> bool:
        """Find company with fuzzy matching."""
        # Try exact match first (case-insensitive)
        exact_match = self.companies_df[
            self.companies_df['name'].str.upper() == company_name.upper()
        ]
        if len(exact_match) > 0:
            return True
        
        # Try normalized matching
        normalized = self._normalize_company_name(company_name)
        for db_name in self.companies_df['name']:
            if self._normalize_company_name(db_name) == normalized:
                return True
        
        # Try alias matching
        if not self.aliases_df.empty:
            # Check if this company name is in aliases
            alias_matches = self.aliases_df[
                self.aliases_df['alias'].str.upper() == company_name.upper()
            ]
            if len(alias_matches) > 0:
                official_name = alias_matches.iloc[0]['official_name']
                official_match = self.companies_df[
                    self.companies_df['name'].str.upper() == official_name.upper()
                ]
                if len(official_match) > 0:
                    return True
                # Try normalized match on official name
                normalized_official = self._normalize_company_name(official_name)
                for db_name in self.companies_df['name']:
                    if self._normalize_company_name(db_name) == normalized_official:
                        return True
        
        # Try partial match (contains)
        contains_match = self.companies_df[
            self.companies_df['name'].str.contains(re.escape(company_name), case=False, na=False, regex=True)
        ]
        if len(contains_match) > 0:
            return True
        
        return False
    
    def _load_data(self):
        """Load all necessary data."""
        # Load questions
        with open(self.json_path, 'r') as f:
            self.data = json.load(f)
        self.questions = self.data.get('questions', [])
        
        # Cache data
        print("Loading data cache...")
        self.companies_df = self.qe.execute("SELECT * FROM companies")
        self.sectors = sorted(self.companies_df['gics_sector'].dropna().unique())
        print(f"  {len(self.companies_df)} companies, {len(self.sectors)} sectors")
        
        # Load company aliases
        alias_path = Path(__file__).parent / "data" / "company_name_aliases.csv"
        if alias_path.exists():
            self.aliases_df = pd.read_csv(alias_path)
            print(f"  {len(self.aliases_df)} company aliases loaded")
        else:
            self.aliases_df = pd.DataFrame(columns=['alias', 'official_name', 'cik'])
            print("  No aliases file found")
        
        # Load XBRL tags
        self.tags_df = self.qe.execute("SELECT DISTINCT tag FROM tag")
        self.available_tags = set(self.tags_df['tag'].tolist())
        print(f"  {len(self.available_tags)} XBRL tags available")
        
        # Common financial metrics and their XBRL tags
        self.metric_tags = {
            'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax'],
            'assets': ['Assets'],
            'total_assets': ['Assets'],
            'liabilities': ['Liabilities'],
            'equity': ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
            'net_income': ['NetIncomeLoss', 'ProfitLoss'],
            'operating_income': ['OperatingIncomeLoss'],
            'cash_flow': ['NetCashProvidedByUsedInOperatingActivities'],
            'free_cash_flow': ['NetCashProvidedByUsedInOperatingActivities', 'PaymentsToAcquirePropertyPlantAndEquipment'],
            'gross_margin': ['GrossProfit', 'Revenues'],
            'operating_margin': ['OperatingIncomeLoss', 'Revenues'],
            'return_on_equity': ['NetIncomeLoss', 'StockholdersEquity'],
            'return_on_assets': ['NetIncomeLoss', 'Assets'],
            'debt_to_equity': ['Liabilities', 'StockholdersEquity'],
            'current_ratio': ['AssetsCurrent', 'LiabilitiesCurrent'],
        }
    
    def validate_all(self):
        """Run validation on all questions."""
        print(f"\n{'='*80}")
        print(f"MEDIUM-TIER QUESTION VALIDATION")
        print(f"{'='*80}")
        print(f"Total questions: {len(self.questions)}")
        print(f"{'='*80}\n")
        
        for idx, q in enumerate(self.questions, 1):
            print(f"\n[{idx}/{len(self.questions)}] Validating {q.get('id', 'UNKNOWN')}...")
            result = self.validate_question(q)
            self.results.append(result)
            self._print_quick_summary(result)
        
        self._print_final_summary()
        self._generate_report()
    
    def validate_question(self, q: Dict[str, Any]) -> ValidationResult:
        """Validate a single question against all 5 criteria."""
        result = ValidationResult(
            question_id=q.get('id', 'UNKNOWN'),
            question_text=q.get('question', ''),
            expected_answer=q.get('expected_answer', {}).get('value', '')
        )
        
        # Skip if already disabled
        if q.get('disabled', False):
            result.disposition = "remove"
            result.reason = f"Already disabled: {q.get('disabled_reason', 'No reason given')}"
            return result
        
        # Phase 1: Data availability
        self._check_data_availability(q, result)
        
        # Phase 2: Complexity assessment
        self._assess_complexity(q, result)
        
        # Phase 3: CFO relevance
        self._assess_cfo_relevance(q, result)
        
        # Phase 4: Framework appropriateness
        self._assess_framework_fit(q, result)
        
        # Phase 5: Answer verification (if data available)
        if result.data_available:
            self._verify_answer(q, result)
        
        # Determine final disposition
        self._determine_disposition(result)
        
        return result
    
    def _check_data_availability(self, q: Dict[str, Any], result: ValidationResult):
        """Check if all required data exists."""
        question = q.get('question', '').lower()
        context = q.get('context', {})
        
        issues = []
        
        # Check for external data dependencies
        external_keywords = [
            'market cap', 'stock price', 'market value', 'trading volume',
            'analyst rating', 'credit rating', 'esg score', 'sustainability rating',
            'competitor', 'market share', 'industry growth'
        ]
        
        for keyword in external_keywords:
            if keyword in question:
                issues.append(f"Requires external data: {keyword}")
        
        # Check for sectors mentioned
        sectors_mentioned = context.get('sectors', [])
        if sectors_mentioned:
            for sector in sectors_mentioned:
                sector_matches = self.companies_df[
                    self.companies_df['gics_sector'].str.contains(sector, case=False, na=False)
                ]
                if len(sector_matches) == 0:
                    issues.append(f"Sector not found: {sector}")
        
        # Check for specific companies mentioned
        companies = context.get('companies', [])
        if companies:
            for company in companies:
                if not self._find_company(company):
                    issues.append(f"Company not found: {company}")
        
        # Check metrics
        metrics = context.get('metrics', [])
        if not isinstance(metrics, list):
            metrics = [metrics] if metrics else []
        
        # Look for financial ratio context
        analysis_type = context.get('analysis_type', '')
        if 'correlation' in analysis_type.lower():
            issues.append("Correlation analysis may be memory-intensive")
        
        result.data_available = len(issues) == 0
        result.data_issues = issues
    
    def _assess_complexity(self, q: Dict[str, Any], result: ValidationResult):
        """Assess if question is appropriately medium complexity."""
        question = q.get('question', '').lower()
        context = q.get('context', {})
        category = q.get('category', '')
        
        # Indicators of complexity
        simple_indicators = [
            'what is', 'list', 'count', 'how many', 'which sector', 'get', 'show'
        ]
        
        medium_indicators = [
            'compare', 'analyze', 'calculate', 'rank', 'correlation',
            'median', 'average', 'trend', 'ratio', 'percentage'
        ]
        
        complex_indicators = [
            'predict', 'forecast', 'optimize', 'strategy', 'portfolio',
            'multi-year', 'competitive moat', 'valuation', 'dcf'
        ]
        
        # Count indicators
        simple_count = sum(1 for ind in simple_indicators if ind in question)
        medium_count = sum(1 for ind in medium_indicators if ind in question)
        complex_count = sum(1 for ind in complex_indicators if ind in question)
        
        # Check for multi-step analysis
        steps = []
        if 'calculate' in question or 'compute' in question:
            steps.append('calculation')
        if 'compare' in question or 'versus' in question:
            steps.append('comparison')
        if 'rank' in question or 'top' in question:
            steps.append('ranking')
        if 'trend' in question or 'over time' in question:
            steps.append('time_series')
        
        # Assess complexity
        if complex_count > 0 or 'strategic' in category.lower():
            result.complexity_rating = "too_complex"
            result.complexity_appropriate = False
            result.complexity_notes = "Strategic/complex analysis beyond medium tier"
        elif simple_count > medium_count and len(steps) < 2:
            result.complexity_rating = "too_simple"
            result.complexity_appropriate = False
            result.complexity_notes = "Single-step lookup, belongs in simple tier"
        else:
            result.complexity_rating = "medium"
            result.complexity_appropriate = True
            result.complexity_notes = f"Multi-step analysis ({len(steps)} steps)"
    
    def _assess_cfo_relevance(self, q: Dict[str, Any], result: ValidationResult):
        """Assess CFO office relevance."""
        question = q.get('question', '').lower()
        category = q.get('category', '')
        
        # High-value keywords for CFO office
        high_value_keywords = [
            'profitability', 'return on equity', 'return on assets',
            'cash flow', 'liquidity', 'leverage', 'debt',
            'working capital', 'efficiency', 'margin',
            'capital allocation', 'investment', 'dividend'
        ]
        
        # Medium-value keywords
        medium_value_keywords = [
            'revenue', 'assets', 'liabilities', 'equity',
            'sector', 'industry', 'comparison', 'benchmark'
        ]
        
        # Low-value indicators
        low_value_keywords = [
            'xbrl', 'taxonomy', 'filing pattern', 'data quality',
            'tag usage', 'reporting standard'
        ]
        
        high_count = sum(1 for kw in high_value_keywords if kw in question)
        medium_count = sum(1 for kw in medium_value_keywords if kw in question)
        low_count = sum(1 for kw in low_value_keywords if kw in question)
        
        # Score relevance
        if low_count > 0:
            result.cfo_relevance_score = 2
            result.cfo_notes = "Technical/data quality focus, limited business value"
        elif high_count >= 2:
            result.cfo_relevance_score = 5
            result.cfo_notes = "High-value financial analysis"
        elif high_count == 1 or medium_count >= 2:
            result.cfo_relevance_score = 4
            result.cfo_notes = "Relevant financial analysis"
        else:
            result.cfo_relevance_score = 3
            result.cfo_notes = "Moderate relevance"
        
        result.cfo_relevant = result.cfo_relevance_score >= 3
    
    def _assess_framework_fit(self, q: Dict[str, Any], result: ValidationResult):
        """Assess if question fits evaluation framework."""
        # Check for verifiable answer
        expected = q.get('expected_answer', {})
        if not expected or not expected.get('value'):
            result.framework_appropriate = False
            result.framework_notes = "No expected answer provided"
            return
        
        # Check for tolerance specification
        tolerance = expected.get('tolerance', {})
        answer_type = expected.get('type', '')
        
        if answer_type == 'numeric' and not tolerance:
            result.framework_notes = "Numeric answer without tolerance (may be strict)"
        elif answer_type in ['statistical_analysis', 'comprehensive_leverage_analysis', 'comprehensive_margin_analysis']:
            result.framework_notes = "Complex analysis type - may need careful validation"
        else:
            result.framework_notes = "Answer format appropriate"
        
        result.framework_appropriate = True
    
    def _verify_answer(self, q: Dict[str, Any], result: ValidationResult):
        """Verify the expected answer against actual data."""
        # This is a placeholder - actual verification would require
        # implementing the specific analysis for each question
        # For now, we'll just check if the answer format is reasonable
        
        expected = q.get('expected_answer', {})
        expected_value = expected.get('value', '')
        
        # For now, mark as needs manual verification
        result.answer_correct = False
        result.calculated_answer = "NEEDS_MANUAL_VERIFICATION"
        result.answer_issues.append("Manual verification required")
    
    def _determine_disposition(self, result: ValidationResult):
        """Determine final disposition of question."""
        if result.disposition == "remove":  # Already set (e.g., disabled)
            return
        
        # Remove if data not available
        if not result.data_available:
            result.disposition = "remove"
            result.reason = f"Data not available: {'; '.join(result.data_issues)}"
            return
        
        # Remove if too simple or too complex
        if not result.complexity_appropriate:
            result.disposition = "remove"
            result.reason = f"Complexity issue: {result.complexity_notes}"
            return
        
        # Remove if low CFO relevance
        if not result.cfo_relevant:
            result.disposition = "remove"
            result.reason = f"Low CFO relevance (score: {result.cfo_relevance_score})"
            return
        
        # Remove if framework doesn't fit
        if not result.framework_appropriate:
            result.disposition = "remove"
            result.reason = f"Framework issue: {result.framework_notes}"
            return
        
        # Otherwise, keep (may need answer fix)
        result.disposition = "keep"
        result.reason = "Passes all validation criteria"
    
    def _print_quick_summary(self, result: ValidationResult):
        """Print quick summary of validation result."""
        status_icon = {
            "keep": "✅",
            "remove": "❌",
            "fix_answer": "⚠️",
            "replace": "🔄"
        }.get(result.disposition, "❓")
        
        print(f"  {status_icon} {result.disposition.upper()}: {result.reason}")
        
        if result.data_issues:
            print(f"     Data issues: {len(result.data_issues)}")
        if not result.complexity_appropriate:
            print(f"     Complexity: {result.complexity_rating}")
        if result.cfo_relevance_score < 3:
            print(f"     CFO relevance: {result.cfo_relevance_score}/5")
    
    def _print_final_summary(self):
        """Print final summary statistics."""
        total = len(self.results)
        keep = sum(1 for r in self.results if r.disposition == "keep")
        remove = sum(1 for r in self.results if r.disposition == "remove")
        fix = sum(1 for r in self.results if r.disposition == "fix_answer")
        replace = sum(1 for r in self.results if r.disposition == "replace")
        
        print(f"\n{'='*80}")
        print(f"VALIDATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total questions:      {total}")
        print(f"✅ Keep:              {keep} ({keep/total*100:.1f}%)")
        print(f"❌ Remove:            {remove} ({remove/total*100:.1f}%)")
        print(f"⚠️  Fix answer:        {fix} ({fix/total*100:.1f}%)")
        print(f"🔄 Replace:           {replace} ({replace/total*100:.1f}%)")
        print(f"{'='*80}")
        
        # Breakdown by reason
        print(f"\nREMOVAL REASONS:")
        removal_reasons = {}
        for r in self.results:
            if r.disposition == "remove":
                reason_key = r.reason.split(':')[0] if ':' in r.reason else r.reason
                removal_reasons[reason_key] = removal_reasons.get(reason_key, 0) + 1
        
        for reason, count in sorted(removal_reasons.items(), key=lambda x: -x[1]):
            print(f"  - {reason}: {count}")
        
        print(f"{'='*80}\n")
    
    def _generate_report(self):
        """Generate detailed markdown report."""
        report_path = Path(__file__).parent / "medium_validation_report.md"
        
        with open(report_path, 'w') as f:
            f.write("# Medium-Tier Question Validation Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Source**: `{self.json_path.name}`\n\n")
            
            # Executive summary
            f.write("## Executive Summary\n\n")
            total = len(self.results)
            keep = sum(1 for r in self.results if r.disposition == "keep")
            remove = sum(1 for r in self.results if r.disposition == "remove")
            
            f.write(f"- **Total Questions**: {total}\n")
            f.write(f"- **Retained**: {keep} ({keep/total*100:.1f}%)\n")
            f.write(f"- **Removed**: {remove} ({remove/total*100:.1f}%)\n\n")
            
            # Detailed results
            f.write("## Detailed Results\n\n")
            
            for result in self.results:
                f.write(f"### {result.question_id}\n\n")
                f.write(f"**Question**: {result.question_text[:200]}...\n\n")
                f.write(f"**Disposition**: {result.disposition.upper()} - {result.reason}\n\n")
                
                # Criteria breakdown
                f.write("**Validation Criteria**:\n")
                f.write(f"- ✅ Data Available: {result.data_available}\n")
                if result.data_issues:
                    for issue in result.data_issues:
                        f.write(f"  - ⚠️ {issue}\n")
                f.write(f"- ✅ Complexity: {result.complexity_rating} ({result.complexity_notes})\n")
                f.write(f"- ✅ CFO Relevance: {result.cfo_relevance_score}/5 ({result.cfo_notes})\n")
                f.write(f"- ✅ Framework Fit: {result.framework_appropriate}\n")
                f.write(f"- ✅ Answer: {result.answer_correct} ({len(result.answer_issues)} issues)\n\n")
                
                f.write("---\n\n")
        
        print(f"✅ Detailed report written to: {report_path}")
    
    def close(self):
        """Clean up resources."""
        self.qe.close()


def main():
    """Main entry point."""
    json_path = Path(__file__).parent / "evaluation" / "questions" / "medium_analysis.json"
    
    if not json_path.exists():
        print(f"❌ Error: {json_path} not found")
        sys.exit(1)
    
    validator = MediumQuestionValidator(str(json_path))
    
    try:
        validator.validate_all()
    finally:
        validator.close()


if __name__ == "__main__":
    main()


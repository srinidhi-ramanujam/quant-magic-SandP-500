"""
Time Series Question Validator

Systematically validates all 40 time series questions against the 5-point checklist:
0. Data Answerability - Can be answered with our dataset?
1. Time Series Nature - Tracks KPIs over time?
2. CFO Relevance - Relevant to finance professionals?
3. Difficulty Level - Appropriate for time series tier?
4. Answer Accuracy - Expected answer correct?
"""

import json
import duckdb
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of validating a single question"""
    question_id: str
    question_text: str
    data_answerable: bool
    is_time_series: bool
    cfo_relevant: bool
    difficulty_appropriate: bool
    answer_accurate: Optional[bool]  # None means skipped
    issues: List[str]
    recommendations: str
    data_findings: Dict


class TSQuestionValidator:
    """Validator for time series questions"""
    
    def __init__(self, data_path: str = "data/parquet"):
        self.data_path = Path(data_path)
        self.conn = None
        self._setup_database()
        
    def _setup_database(self):
        """Setup DuckDB connection with tables"""
        self.conn = duckdb.connect(':memory:')
        
        # Load parquet files (suppress progress bars)
        self.conn.execute(f"SET progress_bar_time = 0")
        self.conn.execute(f"""
            CREATE TABLE num AS 
            SELECT * FROM read_parquet('{self.data_path}/num.parquet')
        """)
        self.conn.execute(f"""
            CREATE TABLE companies AS 
            SELECT * FROM read_parquet('{self.data_path}/companies_with_sectors.parquet')
        """)
        self.conn.execute(f"""
            CREATE TABLE sub AS 
            SELECT * FROM read_parquet('{self.data_path}/sub.parquet')
        """)
        
    def check_companies_exist(self, company_names: List[str]) -> Tuple[List[str], List[str]]:
        """
        Check which companies exist in our database
        Returns: (found_companies, missing_companies)
        """
        found = []
        missing = []
        
        for name in company_names:
            # Try different search patterns
            search_term = name.split()[0].upper()  # First word usually unique
            result = self.conn.execute(f"""
                SELECT name, cik FROM companies 
                WHERE UPPER(name) LIKE '%{search_term}%'
                LIMIT 1
            """).fetchone()
            
            if result:
                found.append(f"{result[0]} (CIK: {result[1]})")
            else:
                missing.append(name)
                
        return found, missing
    
    def check_sector_exists(self, sector: str) -> bool:
        """Check if sector exists in our data"""
        result = self.conn.execute(f"""
            SELECT COUNT(*) FROM companies 
            WHERE gics_sector = '{sector}'
        """).fetchone()
        return result[0] > 0
    
    def check_metrics_available(self, metrics: List[str], sector: str = None, 
                                date_range: Tuple[str, str] = ('2019-01-01', '2023-12-31')) -> Dict:
        """
        Check availability of financial metrics
        Returns dict with metric availability counts
        """
        results = {}
        for metric in metrics:
            query = f"""
                SELECT COUNT(DISTINCT n.adsh) 
                FROM num n
                JOIN sub s ON n.adsh = s.adsh
                JOIN companies c ON s.cik = c.cik
                WHERE n.tag = '{metric}'
                AND n.ddate >= '{date_range[0]}' AND n.ddate <= '{date_range[1]}'
            """
            if sector:
                query += f" AND c.gics_sector = '{sector}'"
                
            count = self.conn.execute(query).fetchone()[0]
            results[metric] = count
            
        return results
    
    def validate_question(self, question_data: Dict) -> ValidationResult:
        """Validate a single time series question"""
        q_id = question_data.get('id', 'UNKNOWN')
        question_text = question_data.get('question', '')
        
        issues = []
        data_findings = {}
        
        # [0] Data Answerability Check
        data_answerable = self._check_data_answerability(question_data, issues, data_findings)
        
        # [1] Time Series Nature Check
        is_time_series = self._check_time_series_nature(question_data, issues)
        
        # [2] CFO Relevance Check
        cfo_relevant = self._check_cfo_relevance(question_data, issues)
        
        # [3] Difficulty Level Check
        difficulty_appropriate = self._check_difficulty_level(question_data, issues)
        
        # [4] Answer Accuracy Check (if expected_answer exists and not placeholder)
        answer_accurate = self._check_answer_accuracy(question_data, issues)
        
        # Determine recommendation
        recommendation = self._generate_recommendation(
            data_answerable, is_time_series, cfo_relevant, 
            difficulty_appropriate, answer_accurate
        )
        
        return ValidationResult(
            question_id=q_id,
            question_text=question_text,
            data_answerable=data_answerable,
            is_time_series=is_time_series,
            cfo_relevant=cfo_relevant,
            difficulty_appropriate=difficulty_appropriate,
            answer_accurate=answer_accurate,
            issues=issues,
            recommendations=recommendation,
            data_findings=data_findings
        )
    
    def _check_data_answerability(self, question_data: Dict, issues: List[str], 
                                   data_findings: Dict) -> bool:
        """Check if question can be answered with our dataset"""
        
        # Extract required data from question
        retrieval_criteria = question_data.get('retrieval_test_criteria', {})
        sector_filter = retrieval_criteria.get('sector_filter', '')
        required_metrics = retrieval_criteria.get('required_metrics', [])
        min_companies = retrieval_criteria.get('min_companies', 0)
        data_span = retrieval_criteria.get('expected_data_span', '')
        
        answerable = True
        
        # Check sector exists
        if sector_filter and sector_filter != 'All':
            if not self.check_sector_exists(sector_filter):
                issues.append(f"❌ Sector '{sector_filter}' not found in database")
                answerable = False
            else:
                # Count companies in sector
                count = self.conn.execute(f"""
                    SELECT COUNT(*) FROM companies WHERE gics_sector = '{sector_filter}'
                """).fetchone()[0]
                data_findings['sector_company_count'] = count
                
                if count < min_companies:
                    issues.append(f"⚠️ Only {count} companies in {sector_filter}, need {min_companies}")
                    answerable = False
        
        # Check metrics availability
        if required_metrics:
            date_range = self._parse_data_span(data_span)
            metric_availability = self.check_metrics_available(
                required_metrics, 
                sector_filter if sector_filter != 'All' else None,
                date_range
            )
            data_findings['metric_availability'] = metric_availability
            
            for metric, count in metric_availability.items():
                if count == 0:
                    issues.append(f"❌ Metric '{metric}' has 0 submissions")
                    answerable = False
                elif count < 10:
                    issues.append(f"⚠️ Metric '{metric}' has only {count} submissions (sparse)")
        
        # Check for external data dependencies (keywords that indicate external data)
        external_keywords = ['ESG', 'WACC', 'cost of capital', 'market share', 'pricing power', 
                            'customer satisfaction', 'brand', 'RegTech', 'cybersecurity incident',
                            'patent', 'R&D productivity', 'talent', 'acquisition cost', 
                            'lifetime value', 'churn rate', 'subscription']
        
        question_lower = question_data.get('question', '').lower()
        for keyword in external_keywords:
            if keyword.lower() in question_lower:
                issues.append(f"⚠️ Question references '{keyword}' which may require external data")
                # Don't mark as unanswerable yet, but flag it
        
        return answerable
    
    def _parse_data_span(self, data_span: str) -> Tuple[str, str]:
        """Parse data span string to date range"""
        # Default to 2019-2023
        if '5 years' in data_span or '5 year' in data_span:
            return ('2019-01-01', '2023-12-31')
        elif '6 years' in data_span or '6 year' in data_span:
            return ('2018-01-01', '2023-12-31')
        elif '7 years' in data_span or '7 year' in data_span:
            return ('2017-01-01', '2023-12-31')
        elif '4 years' in data_span or '4 year' in data_span:
            return ('2020-01-01', '2023-12-31')
        elif '3 years' in data_span or '3 year' in data_span:
            return ('2021-01-01', '2023-12-31')
        else:
            return ('2019-01-01', '2023-12-31')
    
    def _check_time_series_nature(self, question_data: Dict, issues: List[str]) -> bool:
        """Check if question truly represents time series analysis"""
        question_text = question_data.get('question', '').lower()
        
        # Time series indicators
        time_indicators = ['trend', 'over time', 'from', 'to', 'evolution', 'progression',
                          'yoy', 'qoq', 'quarterly', 'annual', 'years', 'quarters',
                          'historical', 'past', 'since', 'through', 'during',
                          'improvement', 'decline', 'change', 'growth', 'pattern']
        
        has_time_element = any(indicator in question_text for indicator in time_indicators)
        
        # Check time_span in metadata
        time_span = question_data.get('time_span', '')
        retrieval_criteria = question_data.get('retrieval_test_criteria', {})
        expected_data_span = retrieval_criteria.get('expected_data_span', '')
        
        has_multi_period = bool(time_span or expected_data_span)
        
        if not has_time_element:
            issues.append("⚠️ Question lacks clear time series language (trend, over time, etc.)")
            
        if not has_multi_period:
            issues.append("⚠️ No multi-period time span specified in metadata")
        
        return has_time_element and has_multi_period
    
    def _check_cfo_relevance(self, question_data: Dict, issues: List[str]) -> bool:
        """Check if question is relevant to CFO office"""
        question_text = question_data.get('question', '').lower()
        business_context = question_data.get('business_context', '').lower()
        category = question_data.get('category', '').lower()
        
        # CFO-relevant indicators
        cfo_topics = [
            'profitability', 'roe', 'roa', 'roic', 'margin', 'revenue', 'cash flow',
            'debt', 'leverage', 'liquidity', 'efficiency', 'capital allocation',
            'working capital', 'financial performance', 'earnings', 'assets', 'equity',
            'investment', 'cost', 'expense', 'financial', 'ratio', 'balance sheet',
            'income statement', 'valuation', 'risk'
        ]
        
        # Strategic CFO topics
        strategic_topics = [
            'strategic', 'capital allocation', 'investment decision', 'risk management',
            'performance measurement', 'competitive', 'value creation', 'shareholder'
        ]
        
        has_financial_topic = any(topic in question_text or topic in business_context or topic in category
                                 for topic in cfo_topics)
        
        has_strategic_relevance = any(topic in question_text or topic in business_context
                                     for topic in strategic_topics)
        
        if not has_financial_topic:
            issues.append("⚠️ Question lacks clear financial/CFO-relevant metrics")
            return False
            
        # Very relevant if has both financial and strategic elements
        return has_financial_topic
    
    def _check_difficulty_level(self, question_data: Dict, issues: List[str]) -> bool:
        """Check if difficulty is appropriate for time series tier"""
        difficulty = question_data.get('difficulty', '').lower()
        
        # Time series should be "medium", "hard", "expert", or "advanced"
        appropriate_levels = ['medium', 'hard', 'expert', 'advanced']
        
        if difficulty not in appropriate_levels:
            issues.append(f"⚠️ Difficulty '{difficulty}' may not be appropriate for time series tier")
            return False
            
        # Check complexity indicators in question
        question_text = question_data.get('question', '').lower()
        
        # Simple question indicators (shouldn't be in time series)
        simple_indicators = ['what is', 'how many', 'list', 'show me', 'find']
        if any(indicator in question_text for indicator in simple_indicators):
            if not any(word in question_text for word in ['trend', 'over', 'progression', 'evolution']):
                issues.append("⚠️ Question structure seems too simple for time series tier")
                return False
        
        return True
    
    def _check_answer_accuracy(self, question_data: Dict, issues: List[str]) -> Optional[bool]:
        """Check if expected answer is accurate (or identify if placeholder)"""
        expected_answer = question_data.get('expected_answer', {})
        
        if not expected_answer:
            issues.append("ℹ️ No expected_answer provided")
            return None
            
        # Check if placeholder
        answer_pattern = expected_answer.get('answer_pattern', '')
        business_insight = expected_answer.get('business_insight', '')
        
        if 'placeholder' in answer_pattern.lower() or 'placeholder' in business_insight.lower():
            issues.append("ℹ️ Expected answer contains placeholders - needs generation")
            return None
        
        # For non-placeholder answers, we'd need to verify against actual data
        # This is complex and question-specific, so we'll flag for manual review
        issues.append("ℹ️ Answer verification requires manual review against actual data")
        return None
    
    def _generate_recommendation(self, data_answerable: bool, is_time_series: bool,
                                cfo_relevant: bool, difficulty_appropriate: bool,
                                answer_accurate: Optional[bool]) -> str:
        """Generate recommendation based on validation results"""
        
        if not data_answerable:
            return "🔄 REPLACE - Cannot be answered with existing dataset"
            
        if not is_time_series:
            return "📋 MOVE - Not truly time series analysis, move to appropriate tier"
            
        if not cfo_relevant:
            return "🔄 REPLACE - Not relevant to CFO office, replace with financial question"
            
        if not difficulty_appropriate:
            return "📋 REVIEW DIFFICULTY - May need tier reassignment"
            
        if answer_accurate is False:
            return "🔧 FIX ANSWER - Question valid but answer needs correction"
            
        if answer_accurate is None:
            return "✏️ GENERATE ANSWER - Question valid but needs expected answer"
            
        return "✅ KEEP AS-IS - Passes all validation checks"
    
    def validate_all_questions(self, json_file: str) -> List[ValidationResult]:
        """Validate all questions in the JSON file"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        questions = data.get('questions', [])
        results = []
        
        print(f"\n{'='*80}")
        print(f"VALIDATING {len(questions)} TIME SERIES QUESTIONS")
        print(f"{'='*80}\n")
        
        for i, question in enumerate(questions, 1):
            q_id = question.get('id', f'Q{i}')
            print(f"[{i}/{len(questions)}] Validating {q_id}...", end=' ')
            
            result = self.validate_question(question)
            results.append(result)
            
            # Quick status
            if result.recommendations.startswith('✅'):
                print("✅ PASS")
            elif result.recommendations.startswith('🔄'):
                print("❌ REPLACE")
            elif result.recommendations.startswith('📋'):
                print("⚠️ REVIEW")
            else:
                print("ℹ️ ACTION NEEDED")
        
        return results
    
    def print_summary_report(self, results: List[ValidationResult]):
        """Print summary report of validation results"""
        total = len(results)
        
        pass_count = sum(1 for r in results if r.recommendations.startswith('✅'))
        replace_count = sum(1 for r in results if r.recommendations.startswith('🔄'))
        review_count = sum(1 for r in results if r.recommendations.startswith('📋'))
        fix_count = sum(1 for r in results if r.recommendations.startswith('🔧'))
        generate_count = sum(1 for r in results if r.recommendations.startswith('✏️'))
        
        print(f"\n{'='*80}")
        print(f"VALIDATION SUMMARY")
        print(f"{'='*80}\n")
        print(f"Total Questions: {total}")
        print(f"✅ Pass (Keep As-Is): {pass_count} ({pass_count/total*100:.1f}%)")
        print(f"🔄 Replace: {replace_count} ({replace_count/total*100:.1f}%)")
        print(f"📋 Review/Move: {review_count} ({review_count/total*100:.1f}%)")
        print(f"🔧 Fix Answer: {fix_count} ({fix_count/total*100:.1f}%)")
        print(f"✏️ Generate Answer: {generate_count} ({generate_count/total*100:.1f}%)")
        
        print(f"\n{'='*80}")
        print(f"CHECKPOINT PASS RATES")
        print(f"{'='*80}\n")
        print(f"[0] Data Answerability: {sum(1 for r in results if r.data_answerable)}/{total} ({sum(1 for r in results if r.data_answerable)/total*100:.1f}%)")
        print(f"[1] Time Series Nature: {sum(1 for r in results if r.is_time_series)}/{total} ({sum(1 for r in results if r.is_time_series)/total*100:.1f}%)")
        print(f"[2] CFO Relevance: {sum(1 for r in results if r.cfo_relevant)}/{total} ({sum(1 for r in results if r.cfo_relevant)/total*100:.1f}%)")
        print(f"[3] Difficulty Appropriate: {sum(1 for r in results if r.difficulty_appropriate)}/{total} ({sum(1 for r in results if r.difficulty_appropriate)/total*100:.1f}%)")
        
    def print_detailed_report(self, results: List[ValidationResult], filter_status: str = None):
        """Print detailed report for specific questions"""
        print(f"\n{'='*80}")
        print(f"DETAILED VALIDATION RESULTS" + (f" - {filter_status}" if filter_status else ""))
        print(f"{'='*80}\n")
        
        for result in results:
            # Filter if requested
            if filter_status:
                if filter_status == "PASS" and not result.recommendations.startswith('✅'):
                    continue
                elif filter_status == "REPLACE" and not result.recommendations.startswith('🔄'):
                    continue
                elif filter_status == "ISSUES" and result.recommendations.startswith('✅'):
                    continue
            
            print(f"\n{'─'*80}")
            print(f"Question ID: {result.question_id}")
            print(f"Question: {result.question_text[:200]}...")
            print(f"\nValidation Results:")
            print(f"  [0] Data Answerable: {'✅' if result.data_answerable else '❌'}")
            print(f"  [1] Time Series: {'✅' if result.is_time_series else '❌'}")
            print(f"  [2] CFO Relevant: {'✅' if result.cfo_relevant else '❌'}")
            print(f"  [3] Difficulty: {'✅' if result.difficulty_appropriate else '❌'}")
            print(f"  [4] Answer Accurate: {'✅' if result.answer_accurate else '⏭️' if result.answer_accurate is None else '❌'}")
            
            if result.data_findings:
                print(f"\nData Findings:")
                for key, value in result.data_findings.items():
                    print(f"  • {key}: {value}")
            
            if result.issues:
                print(f"\nIssues:")
                for issue in result.issues:
                    print(f"  {issue}")
            
            print(f"\nRecommendation: {result.recommendations}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main validation workflow"""
    validator = TSQuestionValidator()
    
    # Validate all questions
    results = validator.validate_all_questions(
        'evaluation/questions/time_series_analysis.json'
    )
    
    # Print summary
    validator.print_summary_report(results)
    
    # Print detailed report for questions with issues
    validator.print_detailed_report(results, filter_status="ISSUES")
    
    validator.close()
    
    return results


if __name__ == "__main__":
    results = main()


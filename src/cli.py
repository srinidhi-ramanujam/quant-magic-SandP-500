"""
CLI - Command-line interface for financial queries.

For Phase 0, supports:
- Single question mode
- JSON output
- Debug mode flag
"""

import sys
import json
import argparse

from src.query_engine import QueryEngine
from src.entity_extractor import get_entity_extractor
from src.sql_generator import get_sql_generator
from src.response_formatter import get_response_formatter
from src.models import QueryResult, FormattedResponse
from src.telemetry import (
    setup_logging,
    get_logger,
    create_request_context,
    log_component_timing,
    log_error,
    generate_telemetry_report,
)


class FinancialCLI:
    """Command-line interface for financial queries."""

    def __init__(self):
        """Initialize CLI with all components."""
        # Setup logging first
        setup_logging()
        self.logger = get_logger()

        # Initialize components
        self.query_engine = QueryEngine()
        self.entity_extractor = get_entity_extractor()
        self.sql_generator = get_sql_generator()
        self.response_formatter = get_response_formatter()

        self.logger.info("FinancialCLI initialized successfully")

    def process_question(
        self, question: str, debug_mode: bool = False
    ) -> FormattedResponse:
        """
        Process a natural language question end-to-end.

        Args:
            question: Natural language question
            debug_mode: Whether to include debug information

        Returns:
            FormattedResponse with answer and metadata
        """
        # Create request context for telemetry
        context = create_request_context(question)

        try:
            # Step 1: Extract entities
            entities = self.entity_extractor.extract(question, context)
            self.logger.info(
                f"[{context.request_id}] Extracted: companies={entities.companies}, "
                f"sectors={entities.sectors}, metrics={entities.metrics}"
            )

            # Step 2: Generate SQL
            generated_sql = self.sql_generator.generate(entities, question, context)

            if not generated_sql:
                raise ValueError("Could not generate SQL query for the question")

            self.logger.info(
                f"[{context.request_id}] Generated SQL: {generated_sql.sql[:100]}..."
            )

            # Step 3: Execute query
            with log_component_timing(context, "query_execution"):
                result_df = self.query_engine.execute(generated_sql.sql)

                query_result = QueryResult(
                    data=result_df,
                    row_count=len(result_df),
                    columns=list(result_df.columns),
                    execution_time_seconds=context.component_timings.get(
                        "query_execution", 0.0
                    ),
                    sql_executed=generated_sql.sql,
                )

            self.logger.info(
                f"[{context.request_id}] Query returned {query_result.row_count} rows"
            )

            # Step 4: Format response
            response = self.response_formatter.format(
                query_result, entities, context, debug_mode=debug_mode
            )

            # Generate telemetry report
            _ = generate_telemetry_report(context, success=True)

            return response

        except Exception as e:
            # Log error and return error response
            log_error(context, e)

            # Generate telemetry report for failure
            _ = generate_telemetry_report(context, success=False, error=str(e))

            # Return formatted error response
            return self.response_formatter.format_error(
                e, context, debug_mode=debug_mode
            )

    def close(self):
        """Close database connections."""
        if self.query_engine:
            self.query_engine.close()
        self.logger.info("FinancialCLI closed")

    def run_interactive(self, debug_mode: bool = False):
        """
        Run interactive REPL mode for asking multiple questions.

        Args:
            debug_mode: Whether to show debug information
        """
        # Print welcome banner
        print("\n" + "=" * 70)
        print("🔮 Quant Magic - S&P 500 Financial Analysis")
        print("=" * 70)
        print("\nAsk questions about S&P 500 companies in natural language.")
        print("\nExamples:")
        print("  - How many companies are in the Technology sector?")
        print("  - What is Apple's CIK?")
        print("  - What sector is Microsoft in?")
        print("\nCommands:")
        print("  - 'exit' or 'quit': Exit the application")
        print("  - 'help': Show this help message")
        print("  - 'debug on/off': Toggle debug mode")
        print("=" * 70 + "\n")

        question_count = 0

        while True:
            try:
                # Prompt for question
                question = input("💬 Ask: ").strip()

                # Handle empty input
                if not question:
                    continue

                # Handle commands
                if question.lower() in ["exit", "quit", "q"]:
                    print("\n👋 Goodbye! Thanks for using Quant Magic.\n")
                    break

                elif question.lower() == "help":
                    print("\n📖 Help:")
                    print("  Ask any question about S&P 500 companies.")
                    print("  Current capabilities (Phase 0):")
                    print("    - Count companies in a sector")
                    print("    - Look up company CIK")
                    print("    - Find company sector\n")
                    continue

                elif question.lower().startswith("debug"):
                    if "on" in question.lower():
                        debug_mode = True
                        print("✅ Debug mode enabled\n")
                    elif "off" in question.lower():
                        debug_mode = False
                        print("✅ Debug mode disabled\n")
                    else:
                        print(
                            f"ℹ️  Debug mode is currently: {'ON' if debug_mode else 'OFF'}\n"
                        )
                    continue

                # Process question
                question_count += 1
                response = self.process_question(question, debug_mode=debug_mode)

                # Display response
                print(f"\n💡 Answer: {response.answer}")

                # Show metadata if debug mode
                if debug_mode and response.metadata:
                    print("\n🔍 Debug Info:")
                    print(f"  Confidence: {response.confidence:.1%}")
                    print(
                        f"  Time: {response.metadata.get('total_time_seconds', 0):.4f}s"
                    )
                    print(f"  Rows: {response.metadata.get('row_count', 0)}")
                    print(f"  Request ID: {response.metadata.get('request_id', 'N/A')}")

                    if (
                        response.debug_info
                        and "component_timings" in response.debug_info
                    ):
                        print("  Component timings:")
                        for comp, timing in response.debug_info[
                            "component_timings"
                        ].items():
                            print(f"    - {comp}: {timing:.4f}s")

                # Show confidence warning if low
                if response.confidence < 0.5:
                    print(
                        f"\n⚠️  Low confidence ({response.confidence:.1%}) - answer may be inaccurate"
                    )

                # Show error if failed
                if not response.success and response.error:
                    print(f"\n❌ Error: {response.error}")

                print()  # Blank line for readability

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!\n")
                break

            except Exception as e:
                self.logger.error(f"Error in interactive mode: {e}", exc_info=True)
                print(f"\n❌ Unexpected error: {e}\n")

        # Print summary
        if question_count > 0:
            print(f"📊 Session summary: Processed {question_count} questions")


def main():
    """Main CLI entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Financial Analysis CLI - Ask questions about S&P 500 companies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (ask multiple questions)
  python -m src.cli --interactive

  # Single question
  python -m src.cli "How many companies in Technology sector?"

  # Single question with debug info
  python -m src.cli "What is Apple's CIK?" --debug

  # JSON output (pretty-printed)
  python -m src.cli "What sector is Microsoft in?" --json --pretty
        """,
    )
    parser.add_argument(
        "question",
        type=str,
        nargs="?",
        help="Natural language question (omit for interactive mode)",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Run in interactive mode (ask multiple questions)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with detailed timing and intermediate results",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output in JSON format (single-shot mode)"
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )

    args = parser.parse_args()

    # Initialize CLI
    cli = FinancialCLI()

    try:
        # Interactive mode
        if args.interactive or not args.question:
            cli.run_interactive(debug_mode=args.debug)
            sys.exit(0)

        # Single-shot mode
        response = cli.process_question(question=args.question, debug_mode=args.debug)

        # Output response
        if args.json:
            output = response.to_dict()

            if args.pretty:
                print(json.dumps(output, indent=2))
            else:
                print(json.dumps(output))
        else:
            # Plain text output
            print(response.answer)

            if args.debug:
                print("\n--- Debug Info ---")
                print(f"Confidence: {response.confidence:.2%}")
                print(f"Time: {response.metadata.get('total_time_seconds', 0):.4f}s")

        # Exit with appropriate code
        sys.exit(0 if response.success else 1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        cli.close()


if __name__ == "__main__":
    main()

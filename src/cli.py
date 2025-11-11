"""
CLI - Command-line interface for financial queries.

For Phase 0, supports:
- Single question mode
- JSON output
- Debug mode flag
"""

import argparse
import json
import sys

from src.config import get_config
from src.models import FormattedResponse
from src.services import QueryService
from src.telemetry import create_request_context, get_logger, setup_logging

from src.llm_guard import (
    LLMAvailabilityError,
    OFFLINE_FALLBACK_HELP,
    ensure_llm_available,
)


class FinancialCLI:
    """Command-line interface for financial queries."""

    def __init__(self, allow_offline: bool = False):
        """Initialize CLI with all components."""
        # Setup logging first
        setup_logging()
        self.logger = get_logger()

        # Load configuration and initialize components
        self.config = get_config()
        self.allow_offline = allow_offline

        if not self.allow_offline:
            ensure_llm_available("Financial CLI startup")

        self.query_service = QueryService(
            config=self.config, use_llm=not self.allow_offline
        )

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
        result = self.query_service.run(question, debug_mode=debug_mode)
        return result.response

    def close(self):
        """Close database connections."""
        if self.query_service:
            self.query_service.close()
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
                try:
                    response = self.process_question(question, debug_mode=debug_mode)
                    question_count += 1
                except LLMAvailabilityError:
                    print(f"\n❌ {OFFLINE_FALLBACK_HELP}\n")
                    break

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

            except LLMAvailabilityError:
                print(f"\n❌ {OFFLINE_FALLBACK_HELP}\n")
                break
            except Exception as e:
                self.logger.error(f"Error in interactive mode: {e}", exc_info=True)
                print(f"\n❌ Unexpected error: {e}\n")

        # Print summary
        if question_count > 0:
            print(f"📊 Session summary: Processed {question_count} questions")

    def test_entity_extraction(self, question: str, use_llm: bool = False):
        """
        Test entity extraction on a question (Stage 1 testing).

        Args:
            question: Natural language question
            use_llm: Whether to use LLM-assisted extraction
        """
        from src.entity_extractor import EntityExtractor

        # Create entity extractor with specified mode
        extractor = EntityExtractor(use_llm=use_llm, config=self.config)
        context = create_request_context(question)

        print(
            f"\n🔬 Testing Entity Extraction ({'LLM mode' if use_llm else 'Deterministic mode'})"
        )
        print(f"❓ Question: {question}\n")

        try:
            # Extract entities
            entities = extractor.extract(question, context)

            # Display results
            print("✅ Extraction Results:")
            print(
                f"  Companies: {entities.companies if entities.companies else '(none)'}"
            )
            print(f"  Metrics: {entities.metrics if entities.metrics else '(none)'}")
            print(f"  Sectors: {entities.sectors if entities.sectors else '(none)'}")
            print(
                f"  Time Periods: {entities.time_periods if entities.time_periods else '(none)'}"
            )
            print(f"  Question Type: {entities.question_type}")
            print(f"  Confidence: {entities.confidence:.2%}")

            # Show telemetry if LLM was used
            llm_calls = context.metadata.get("llm_calls", [])
            if use_llm and llm_calls:
                print(f"\n📊 LLM Call Stats:")
                for i, call in enumerate(llm_calls, 1):
                    print(f"  Call {i}:")
                    print(f"    - Stage: {call.get('stage', 'N/A')}")
                    print(f"    - Success: {call.get('success', False)}")
                    print(f"    - Latency: {call.get('latency_ms', 0)}ms")
                    print(f"    - Tokens: {call.get('tokens', {})}")

            # Show timing
            total_time = sum(context.component_timings.values())
            print(f"\n⏱️  Total Time: {total_time:.4f}s")

            return entities

        except Exception as e:
            print(f"\n❌ Error: {e}")
            self.logger.error(f"Entity extraction test failed: {e}", exc_info=True)
            return None


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
    parser.add_argument(
        "--test-entity-extraction",
        action="store_true",
        help="Test entity extraction only (Stage 1) - shows extracted entities, confidence, and LLM stats",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM-assisted entity extraction (for --test-entity-extraction)",
    )
    parser.add_argument(
        "--allow-offline",
        action="store_true",
        help="Bypass Azure OpenAI availability checks and run in deterministic mode",
    )

    args = parser.parse_args()

    # Initialize CLI
    try:
        cli = FinancialCLI(allow_offline=args.allow_offline)
    except LLMAvailabilityError:
        print(f"\n❌ {OFFLINE_FALLBACK_HELP}\n")
        sys.exit(2)

    try:
        # Test entity extraction mode (Stage 1)
        if args.test_entity_extraction:
            if not args.question:
                print("❌ Error: Please provide a question to test entity extraction")
                print(
                    'Example: python -m src.cli "What is Apple\'s CIK?" --test-entity-extraction --use-llm'
                )
                sys.exit(1)
            cli.test_entity_extraction(args.question, use_llm=args.use_llm)
            sys.exit(0)

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

    except LLMAvailabilityError:
        print(f"\n❌ {OFFLINE_FALLBACK_HELP}\n")
        sys.exit(2)
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

"""
Accuracy Testing Script for Phase 1.0.5 Step 2

Tests 18 diverse queries across 4 categories:
- Direct article queries (3)
- Specific calculation queries (4)
- Concept/topic queries (5)
- Vague/clarification queries (4)
- Multi-turn conversations (2 sequences)

Target: 90%+ accuracy, 3+ citations for clear queries
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.containers import get_chat_orchestrator
from core import get_logger

logger = get_logger(__name__)


class AccuracyTester:
    """Run and evaluate accuracy tests."""
    
    def __init__(self):
        self.orchestrator = get_chat_orchestrator()
        self.results = []
        self.session_id = f"test_session_{int(time.time())}"
    
    async def run_single_query(
        self,
        query: str,
        test_id: str,
        expected: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a single query test."""
        
        print(f"\n{'-'*80}")
        print(f"Test ID: {test_id}")
        print(f"Query: {query}")
        print(f"Expected: {expected.get('type', 'unknown')}")
        
        start_time = time.time()
        
        # Use provided conversation_id or create new one
        if conversation_id is None:
            conversation_id = f"conv_{test_id}"
        
        try:
            # Run chat
            response = await self.orchestrator.process_message(
                session_id=self.session_id,
                conversation_id=conversation_id,
                user_message=query,
                language="en"
            )
            
            latency = time.time() - start_time
            
            # Evaluate response
            evaluation = self._evaluate_response(response, expected)
            evaluation['latency'] = latency
            evaluation['test_id'] = test_id
            evaluation['query'] = query
            
            # Print results
            status = "[PASS]" if evaluation['passed'] else "[FAIL]"
            print(f"\nResult: {status}")
            print(f"Latency: {latency:.2f}s")
            
            if response.get('metadata', {}).get('is_clarification'):
                print(f"Clarification: {response.get('content', '')[:100]}")
                suggestions = response.get('suggestions', [])
                print(f"Suggestions: {len(suggestions)}")
                for idx, suggestion in enumerate(suggestions[:3], 1):
                    label = suggestion.get('label', suggestion) if isinstance(suggestion, dict) else str(suggestion)
                    print(f"  {idx}. {label}")
            else:
                content = response.get('content', '')
                citations = response.get('citations', [])
                print(f"Answer: {content[:150]}...")
                print(f"Citations: {len(citations)}")
                for idx, citation in enumerate(citations[:3], 1):
                    source = citation.get('source', 'Unknown') if isinstance(citation, dict) else str(citation)
                    print(f"  {idx}. {source}")
            
            if evaluation.get('issues'):
                print(f"\nIssues:")
                for issue in evaluation['issues']:
                    print(f"  - {issue}")
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Test {test_id} failed: {str(e)}", exc_info=True)
            return {
                'test_id': test_id,
                'query': query,
                'passed': False,
                'error': str(e),
                'latency': time.time() - start_time
            }
    
    def _evaluate_response(
        self,
        response: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate response against expectations."""
        
        issues = []
        passed = True
        
        expected_type = expected.get('type')
        is_clarification = response.get('metadata', {}).get('is_clarification', False)
        
        # Check for clarification vs grounded answer
        if expected_type == 'clarification':
            if not is_clarification:
                issues.append("Expected clarification but got answer")
                passed = False
            else:
                # Check suggestion count
                min_followups = expected.get('min_followups', 3)
                suggestions = response.get('suggestions', [])
                if len(suggestions) < min_followups:
                    issues.append(f"Expected {min_followups}+ follow-ups, got {len(suggestions)}")
                    passed = False
                
                # Check content keywords in suggestions
                should_contain = expected.get('should_contain', [])
                suggestion_text = ' '.join([
                    str(s.get('label', s)) if isinstance(s, dict) else str(s) 
                    for s in suggestions
                ]).lower()
                for keyword in should_contain:
                    if keyword.lower() not in suggestion_text:
                        issues.append(f"Missing expected keyword in suggestions: '{keyword}'")
        
        elif expected_type in ['grounded_answer', 'direct_lookup', 'context_aware']:
            if is_clarification:
                # Check if clarification was expected
                if expected.get('no_clarification'):
                    issues.append("Got clarification when context-aware answer expected")
                    passed = False
            else:
                # Check citations
                citations = response.get('citations', [])
                min_citations = expected.get('min_citations', 1)
                if len(citations) < min_citations:
                    issues.append(f"Expected {min_citations}+ citations, got {len(citations)}")
                    passed = False
                
                # Check content keywords
                content = response.get('content', '').lower()
                should_contain = expected.get('should_contain', [])
                for keyword in should_contain:
                    if keyword.lower() not in content:
                        issues.append(f"Missing expected keyword in answer: '{keyword}'")
        
        return {
            'passed': passed,
            'issues': issues,
            'response_type': 'clarification' if is_clarification else 'answer',
            'citation_count': len(response.get('citations', [])),
            'suggestion_count': len(response.get('suggestions', []))
        }
    
    async def run_multi_turn_test(
        self,
        test_id: str,
        turns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Run a multi-turn conversation test."""
        
        print(f"\n{'='*80}")
        print(f"MULTI-TURN TEST: {test_id}")
        print(f"{'='*80}")
        
        results = []
        # Use SAME conversation_id for all turns to maintain context
        conversation_id = f"conv_{test_id}"
        
        for turn_idx, turn in enumerate(turns, 1):
            print(f"\n  Turn {turn_idx}/{len(turns)}")
            
            result = await self.run_single_query(
                query=turn['query'],
                test_id=f"{test_id}_turn{turn_idx}",
                expected=turn['expected'],
                conversation_id=conversation_id  # Pass shared conversation_id
            )
            
            results.append(result)
        
        return results
    
    async def run_all_tests(self, test_file: str):
        """Run all tests from JSON file."""
        
        print("\n" + "="*80)
        print("ACCURACY TESTING - PHASE 1.0.5 STEP 2")
        print("="*80)
        print(f"Test File: {test_file}")
        print(f"Session ID: {self.session_id}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load test queries
        with open(test_file, 'r') as f:
            tests = json.load(f)
        
        print(f"\nTotal Tests: {len(tests)}")
        
        # Run tests by category
        categories = {
            'direct_article': [],
            'specific_calculation': [],
            'concept_topic': [],
            'vague_clarification': [],
            'multi_turn': []
        }
        
        for test in tests:
            category = test.get('category')
            
            if category == 'multi_turn':
                results = await self.run_multi_turn_test(
                    test_id=test['id'],
                    turns=test['turns']
                )
                categories['multi_turn'].extend(results)
            else:
                result = await self.run_single_query(
                    query=test['query'],
                    test_id=test['id'],
                    expected=test['expected']
                )
                categories[category].append(result)
            
            # Small delay between tests
            await asyncio.sleep(0.5)
        
        # Generate report
        self._generate_report(categories)
    
    def _generate_report(self, categories: Dict[str, List[Dict[str, Any]]]):
        """Generate test summary report."""
        
        print("\n" + "="*80)
        print("TEST SUMMARY REPORT")
        print("="*80)
        
        total_tests = 0
        total_passed = 0
        total_latency = 0
        
        for category, results in categories.items():
            if not results:
                continue
            
            passed = sum(1 for r in results if r.get('passed'))
            total = len(results)
            avg_latency = sum(r.get('latency', 0) for r in results) / total
            
            total_tests += total
            total_passed += passed
            total_latency += sum(r.get('latency', 0) for r in results)
            
            status = "✅" if passed == total else "⚠️" if passed >= total * 0.8 else "❌"
            
            print(f"\n{category.replace('_', ' ').title()}: {status}")
            print(f"  Passed: {passed}/{total} ({100*passed/total:.1f}%)")
            print(f"  Avg Latency: {avg_latency:.2f}s")
            
            # Show failed tests
            failed = [r for r in results if not r.get('passed')]
            if failed:
                print(f"  Failed Tests:")
                for fail in failed:
                    print(f"    - {fail.get('test_id')}: {fail.get('query', '')[:50]}")
                    if fail.get('issues'):
                        for issue in fail['issues']:
                            print(f"        • {issue}")
        
        # Overall metrics
        accuracy = 100 * total_passed / total_tests if total_tests > 0 else 0
        avg_latency = total_latency / total_tests if total_tests > 0 else 0
        
        print(f"\n{'='*80}")
        print(f"OVERALL RESULTS")
        print(f"{'='*80}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {total_passed}")
        print(f"Failed: {total_tests - total_passed}")
        print(f"Accuracy: {accuracy:.1f}%")
        print(f"Avg Latency: {avg_latency:.2f}s")
        
        # Check targets
        print(f"\n{'='*80}")
        print(f"TARGET ACHIEVEMENT")
        print(f"{'='*80}")
        
        targets = [
            ("Accuracy ≥ 90%", accuracy >= 90),
            ("Avg Latency < 9s", avg_latency < 9),
        ]
        
        for target, achieved in targets:
            status = "✅ PASS" if achieved else "❌ FAIL"
            print(f"{status}: {target}")
        
        # Save detailed results
        output_file = Path(__file__).parent.parent / 'tests' / 'data' / 'accuracy_results.json'
        all_results = []
        for results in categories.values():
            all_results.extend(results)
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id,
                'summary': {
                    'total_tests': total_tests,
                    'passed': total_passed,
                    'failed': total_tests - total_passed,
                    'accuracy': accuracy,
                    'avg_latency': avg_latency
                },
                'results': all_results
            }, f, indent=2)
        
        print(f"\nDetailed results saved to: {output_file}")
        print(f"{'='*80}\n")


async def main():
    """Main entry point."""
    
    test_file = Path(__file__).parent.parent / 'tests' / 'data' / 'accuracy_test_queries.json'
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return
    
    tester = AccuracyTester()
    await tester.run_all_tests(str(test_file))


if __name__ == "__main__":
    print("\nStarting accuracy tests...")
    print("Ensure backend is running with populated database\n")
    
    try:
        asyncio.run(main())
        print("\n✅ Accuracy testing completed!\n")
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user\n")
    except Exception as e:
        print(f"\n❌ Testing failed: {str(e)}\n")
        import traceback
        traceback.print_exc()

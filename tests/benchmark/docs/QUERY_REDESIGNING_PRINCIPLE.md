Thoroughly check the status documented in HYBRID_REDESIGN_TRACKER.md especially the policies for query redesign.
Follow similar workflow from lexical scenario below.

- Follow the redesign guide properties
- Focus on one queries for each debugging session to enable thorough investigation
- Created/Update Lexical_REDESIGN_TRACKER to keep track of all target query status
- Check the current queries, confirm some validities againt the actual kb/chunks/* data, confim validity againts the embedding data
- Test if it passes using benchmark runner targeted query-ids command to save tokens.
python -m tests.benchmark.runner --mode retrieval_only --top-k 3 5 10
--variant dense_only lexical_only
--query-ids Q001 --output-dir tests/benchmark/results/dry_run_lexical

- important principle: saving tokens
- Iterate fixing if failed. Focus on fixing query issues one by one so we do not waste LLM tokens.
- If fixing attempt reaches more than 6, consider relaxing the threshold (as long as the overall condition is met) for the goal (saving tokens)
- do not run full batch confirmation. The individual fixing and confirmation should be enough unless the source code..
- Document fixes and updated Lexical_REDESIGN_TRACKER

Continue redesigning hybrid target queries using the same workflow.

- For multi-turn hybrid queries, make sure that the clarification answer query (turn3_response) in the conversation_history is answering the new clarification_question (turn2_query) and update the benchmark_query.json.
- Make sure the query properties are retained. Ex. Multi-turn/ambiguous type, query_text correctly match with language.
- Non-negotiable: Check the current Design Properties we have created but I do not care what query-property you use but you need to explore all possibilities to successfully redesign them.
- if you are stuck in a loop let me know and summarized so I can review and suggest a direction.
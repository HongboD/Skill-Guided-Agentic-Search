# Skill derivation and final text


The skills translate published search behavior into short instructions for a searcher.
Each skill uses three source documents.
The derivation retains supported search actions and stopping advice.
It removes database-specific syntax and advice for interface designers.
The common prompt supplies the task's relevance criteria and tool syntax.

| Condition | Search procedure | Source basis |
|---|---|---|
| S0 | Common task prompt, without an added strategy block. | Baseline condition. |
| S1 | Use specific clues, narrow the search, change one concept at a time, and verify against the request. | Marcia J. Bates, *Information Search Tactics* (1979); Jin Ha Lee, Allen Renear, and Linda C. Smith, *Known-Item Search: Variations on a Concept* (2007); Stephen P. Harter and Anne Rogers Peters, *Heuristics for online information retrieval: a typology and preliminary listing* (1985). |
| S2 | Read starting records, follow content leads, and develop the search focus from encountered information. | Marcia J. Bates, *The design of browsing and berrypicking techniques for the online search interface* (1989); David Ellis, *A behavioural approach to information retrieval system design* (1989); Carol C. Kuhlthau, *Inside the search process: Information seeking from the user's perspective* (1991). |
| S3 | Expand wording for the same request, inspect new results, and test queries against known useful records. | David C. Blair and M. E. Maron, *An evaluation of retrieval effectiveness for a full-text document-retrieval system* (1985); *Cochrane Handbook for Systematic Reviews of Interventions*, Chapter 4, *Searching for and selecting studies*; Wichor M. Bramer and colleagues, *A systematic approach to searching: an efficient and complete method to develop literature searches* (2018). |
| S4 | Repeat the task goal after the common prompt. | Objective repetition control. |

S1 to S3 use the same four headings and five numbered search steps.
S1 contains 170 words, S2 contains 164 words, and S3 contains 161 words.
These counts exclude headings and step numbers.
The skill blocks omit author names, citations, strategy labels, dataset names, and metric names.
They use qualitative stopping rules.
The derivation links each substantive instruction to a source passage.
The researcher record gives the source, page, and a short supporting quote.
Only the skill text enters the model prompt.

S2 follows terms, names, and ideas in retrieved text.
These content leads fit the available search box and document-reading tool.
The request's goal stays fixed while the focus of a query can change.
S3 revises the wording used to retrieve material for the same request.

The prompt asks the model to apply its assigned skill throughout the task.
The controller validates tool use and output format.
It does not force a search sequence or require a rationale before each search.
S4 repeats one objective and is shorter than the procedural skills.

## Exact S1 text

```text
# Search Strategy

## Objective

Search the provided collection using specific descriptions of what is sought, checking the search against the original request.

## Search Process

1. Use the identifying details supplied in the request to formulate the search, without assuming they are complete or correct.
2. Where possible, begin with the most specific term or concept in the request, likely to yield the fewest results.
3. If results are too broad, add another element of the request or reduce alternative terms for the same concept, keeping those that describe it most closely.
4. When adding or deleting terms, change one concept at a time so you can connect the change to its effect on retrieval.
5. Compare the current search with the original request and correct spelling or factual errors; question an empty result before treating it as absence of material.

## Handling Findings

Read retrieved documents to check the search and identify flaws in its formulation.

## Stopping

Stop pursuing a candidate once it has been verified against the request. End the search when the expected benefit of another specific search no longer justifies the effort.
```

## Exact S2 text

```text
# Search Strategy

## Objective

Let the search evolve as you read the provided collection, using encountered information to reshape queries and suggest further directions.

## Search Process

1. Begin with a topic search to find starting documents, then skim and read them to become informed about the topic.
2. Use terms, names, and ideas found in the documents you read as leads for further searches in the collection.
3. Browse within areas of potential interest, scanning for material worth reading or following up.
4. Develop a focus from ideas encountered while reading, and revise queries and search terms as the information suggests new directions.
5. Revisit and combine these activities as the search develops, choosing search methods suited to your current needs.

## Handling Findings

Gather useful documents and pieces of information throughout the search, building the findings from successive selections made along different search paths.

## Stopping

Stop following a lead when the same material recurs or new material adds little to what you have learned. End the search when further searching mostly turns up information you have already encountered.
```

## Exact S3 text

```text
# Search Strategy

## Objective

Search the provided collection, iteratively revising search terms for the same request using wording found in retrieved documents.

## Search Process

1. Identify the question’s key concepts, keeping the number of required concepts small to avoid unnecessarily excluding relevant documents.
2. Search using alternative terms for each concept, including synonyms, spelling variants, and abbreviations; allow any alternative to match within each concept.
3. Broaden the query with additional terms and compare results with the previous search, examining documents retrieved only by the broader query.
4. Read retrieved documents for additional wording, including unexpected descriptions of the same subject, and use those expressions in further searches.
5. Check that the search retrieves relevant documents already found in the collection; investigate missed documents by testing each query concept separately against those documents, and revise the search.

## Handling Findings

Combine results from the searches and remove duplicate records.

## Stopping

Consider stopping query development when a series of added terms yields no new relevant documents. Be more cautious about stopping when little evidence has been found.
```

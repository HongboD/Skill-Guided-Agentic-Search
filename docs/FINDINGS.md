# Search-strategy skills: results and actions across three models

**Skills change search behavior more consistently than they improve retrieval.** GPT S3 improves systematic-review retrieval. DeepSeek S2 reduces it. Query generation and final query selection can have different effects. A session can retrieve useful studies, then leave them out of its final result.

## Research questions and evidence

1. **RQ1: When do skills improve or reduce retrieval quality?**
2. **RQ2: How do skills change search actions, and where is retrieved evidence lost?**
3. **RQ3: What effort accompanies the gains and losses?**

The comparison contains **3,240 accepted sessions**: 1,080 each for **GPT-6.1 Sol**, **Claude Sonnet 5.5**, and **DeepSeek-V4.1-Flash**. Each model completes S0–S4 on the same 150 ToT 2023 topics, 36 Genomics 2007 topics, and 30 TAR 2018 topics. TAR uses the original full collection. All 3,240 sessions were conducted by the common Python search agent; GPT, Claude Sonnet, and DeepSeek are the model backends. All three use the same execution setup, with no session time limit or model-specific settings for ToT runs.

**S0** supplies no strategy. **S1** uses specific constraints and checks findings against the request. **S2** follows terms and ideas from retrieved content. **S3** expands wording for the same request. **S4** repeats the goal without a search procedure.

Behavior measurements use neutral action records, exact tool results, and the evidence available before each response batch. Model and condition labels are joined after measurement. Official scores come from accepted evaluations. The unit of comparison is a topic within a task and model. Cross-model rows describe the observed results; task metrics remain separate.

The planned tests compare S1–S4 with S0. They use 10,000 paired bootstrap samples and two-sided sign randomization, with 100,000 random samples for these topic sets. The seed is 20261029. Holm correction covers four contrasts within each model and task. New behavior and selection diagnostics are exploratory. Their unadjusted 95% intervals use 10,000 paired-topic bootstrap samples, with seed 20261106.

## Search actions and final output

`search(query, offset)` uses Lucene BM25 and returns up to 20 hits per page. Results include the total hit count, query ID, document IDs, titles, scores, and text previews of up to 600 characters. `open(doc_id)` returns the stored text of a result already shown. `finish(query_ids)` selects one to three executed queries with different text. Reciprocal rank fusion, with constant 60, forms the final ranking. Its depth is up to 1,000 results for ToT and Genomics, and 5,000 for TAR. The model chooses queries, documents to open, and when to finish.

## RQ1: Retrieval gains and losses

The table gives official mean scores. Higher is better. ToT uses NDCG@1000 to measure the rank of the target film. Genomics uses Aspect MAP to measure retrieval across biomedical answer aspects. TAR uses Recall@5000: the fraction of relevant studies in the first 5,000 results.

| Task and metric | Model | S0 | S1 | S2 | S3 | S4 |
|---|---|---:|---:|---:|---:|---:|
| ToT: NDCG@1000 | GPT | 0.8808 | 0.8866 | 0.9064 | 0.8869 | 0.8561 |
| ToT: NDCG@1000 | Claude | 0.6043 | 0.5653 | 0.5841 | 0.6078 | 0.6089 |
| ToT: NDCG@1000 | DeepSeek | 0.6661 | 0.6824 | 0.7130 | 0.6902 | 0.7146 |
| Genomics: Aspect MAP | GPT | 0.3672 | 0.3222 | 0.3647 | 0.3340 | 0.3460 |
| Genomics: Aspect MAP | Claude | 0.3324 | 0.3291 | 0.3010 | 0.3561 | 0.3561 |
| Genomics: Aspect MAP | DeepSeek | 0.3066 | 0.2929 | 0.3012 | 0.3317 | 0.2948 |
| TAR: Recall@5000 | GPT | 0.9002 | 0.9019 | 0.8771 | 0.9478 | 0.8906 |
| TAR: Recall@5000 | Claude | 0.7844 | 0.7423 | 0.7895 | 0.7698 | 0.8123 |
| TAR: Recall@5000 | DeepSeek | 0.7466 | 0.6154 | 0.5780 | 0.6718 | 0.6904 |

Two contrasts pass the planned within-task correction:

| Contrast | Mean change | 95% paired interval | Wins / ties / losses | Adjusted p |
|---|---:|---|---|---:|
| GPT TAR S3 − S0 | +0.0477 | [+0.0160, +0.0841] | 13 / 16 / 1 | 0.0218 |
| DeepSeek TAR S2 − S0 | -0.1686 | [-0.2901, -0.0609] | 6 / 9 / 15 | 0.0253 |

GPT S3 gains recall on 13 TAR topics and loses on one. DeepSeek S2 loses recall on 15 topics and gains on six. The same task can therefore show a useful skill effect for one model and a harmful effect for another skill and model.

A wider exploratory correction covers all 27 S1–S3 contrasts. Adjusted p values are 0.1471 for GPT S3 TAR and 0.1643 for DeepSeek S2 TAR. Neither passes 0.05. The planned tests support the two specific findings above. They do not support a general gain from skills.

A separate exploratory test compares each skill with S4. Across these 27 comparisons, only GPT S3 TAR passes Holm correction: gain 0.0573, interval [0.0213, 0.1093], adjusted p = 0.0121. Thus, this gain also exceeds the repeated-goal control. S4 does not control for instruction length. The 27 exploratory tests of differences in skill gains between models yield no adjusted p below 0.05.

The highest means also differ by task. S3 has the highest Genomics mean for DeepSeek and shares the highest rounded mean for Claude. S0 has the highest GPT Genomics mean. S4 has the highest ToT mean for Claude and DeepSeek. On TAR, all four DeepSeek instruction conditions score below S0. None of these remaining contrasts passes the planned correction. A repeated goal can be competitive with procedural text.

GPT S0 already scores 1.0 on 129 of 150 ToT topics. The corresponding counts are 78 for Claude and 97 for DeepSeek. The available room for improvement differs. A gain can recover a missed film or improve its rank.

## RQ2: Search behavior and evidence retention

Mean successful search calls per session are shown below. Counts include zero-hit queries and paging. Repeated query text remains part of the behavior count.

| Task | Model | S0 | S1 | S2 | S3 | S4 |
|---|---|---:|---:|---:|---:|---:|
| ToT | GPT | 11.4 | 11.5 | 10.8 | 12.2 | 11.5 |
| ToT | Claude | 19.5 | 19.4 | 19.2 | 21.3 | 19.5 |
| ToT | DeepSeek | 128.9 | 109.0 | 142.4 | 125.5 | 125.2 |
| Genomics | GPT | 14.2 | 12.2 | 16.1 | 18.4 | 13.7 |
| Genomics | Claude | 7.1 | 6.9 | 10.5 | 10.0 | 7.0 |
| Genomics | DeepSeek | 57.6 | 51.1 | 69.9 | 61.6 | 52.5 |
| TAR | GPT | 18.4 | 20.1 | 23.2 | 25.1 | 20.1 |
| TAR | Claude | 8.5 | 8.8 | 13.4 | 10.7 | 9.0 |
| TAR | DeepSeek | 52.5 | 55.0 | 75.2 | 56.8 | 56.3 |

On ToT, S0 median search counts are 3 for GPT, 15 for Claude, and 53 for DeepSeek. The higher means show a tail of long sessions. In DeepSeek S0, the mean within-session zero-hit rate is 17.7%. Its repeated-query-text rate is 1.5%, including paging. The high search count therefore includes many different query strings. Different text alone does not establish useful progress.

The next table shows how S2 changes three behaviors relative to S0. Query diversity is the mean pairwise Jaccard distance between query term sets. Lexical adoption is the share of post-first searches with a new term found in earlier delivered evidence. A new term is absent from the request and earlier queries. Same-batch tool results cannot support that adoption. Changes in adoption are percentage points.

| Task | Model | Query-diversity change | Record-open change | Lexical-adoption change |
|---|---|---:|---:|---:|
| ToT | GPT | +0.063 | +0.1 | +7.4 |
| ToT | Claude | +0.015 | +0.0 | +3.8 |
| ToT | DeepSeek | +0.002 | +1.8 | +1.4 |
| Genomics | GPT | +0.030 | +6.0 | +0.6 |
| Genomics | Claude | +0.032 | +0.5 | +11.5 |
| Genomics | DeepSeek | +0.029 | +0.9 | +6.4 |
| TAR | GPT | +0.044 | +9.1 | -0.9 |
| TAR | Claude | +0.018 | +0.1 | +7.7 |
| TAR | DeepSeek | +0.011 | +4.6 | -7.4 |

The S2 diversity comparison uses 145 paired GPT ToT topics, 147 Claude topics, and 150 DeepSeek topics. All biomedical topics enter that comparison. The measure requires at least two nonempty query term sets.

### Shared trends under the same skill and task

**S2 on Genomics gives the clearest shared response.** All three models use more varied query wording, make more searches, and use more tokens. The table shows changes from S0 on the same topics.

| S2 Genomics measure | GPT | Claude | DeepSeek |
|---|---:|---:|---:|
| Query-diversity change | +0.030 | +0.032 | +0.029 |
| Search-count change | +13.3% | +49.2% | +21.5% |
| Token-use change | +34.7% | +72.0% | +71.3% |
| Aspect MAP change | -0.0026 | -0.0313 | -0.0053 |

The query-diversity increases are almost equal. Each exploratory 95% interval excludes zero. All three mean scores fall, but none of these score decreases passes the adjusted test. S2 therefore shows a shared behavior change without a demonstrated quality gain.

S2 increases mean query diversity on both biomedical tasks for all three models. The balance between searching and reading differs. On Genomics, S2 changes distinct parent documents opened per search by +0.216 for GPT, +0.035 for Claude, and −0.029 for DeepSeek. DeepSeek makes more open calls, but its search count grows faster.

**S3 on Genomics gives Claude and DeepSeek a similar positive score trend.** Claude makes 41.7% more searches and gains 0.0237 Aspect MAP. DeepSeek makes 7.1% more searches and gains 0.0251. GPT also searches more, but its score falls by 0.0333. These score changes do not pass the adjusted tests. The shared direction has different effort costs.

**Other shared directions also appear.** S1 lowers mean search count and mean Genomics score for all three models. Its query-diversity changes are −0.063 for GPT, −0.007 for Claude, and +0.008 for DeepSeek. S3 raises mean search count on both biomedical tasks for all three models. On ToT, S3 raises all three mean scores. GPT and Claude search more, while DeepSeek searches less.

On TAR, the lexical-adoption share changes by −0.9 percentage points for GPT, +7.7 for Claude, and −7.4 for DeepSeek. A lower share can accompany more adoption events if the search count also increases. These measures describe action patterns and lexical evidence use.

These are task-level mean trends. They do not establish that models take similar steps on every topic. Which models look similar depends on the task and the measure.

### Retrieved evidence and final selection

**TAR shows a large loss at final selection.** Pool coverage counts relevant studies anywhere in the saved query rankings. The pool can exceed 5,000 studies and includes results never shown to the model. Selected recall uses the final output. The gap is pool coverage minus selected recall. Exact diagnostic recall can differ slightly from the rounded official score.

| Model | Condition | Pool coverage | Selected recall | Gap |
|---|---|---:|---:|---:|
| GPT | S0 | 0.9317 | 0.9001 | 0.0316 |
| GPT | S2 | 0.9376 | 0.8770 | 0.0605 |
| GPT | S3 | 0.9524 | 0.9478 | 0.0046 |
| Claude | S0 | 0.9415 | 0.7844 | 0.1571 |
| Claude | S2 | 0.9485 | 0.7895 | 0.1590 |
| Claude | S3 | 0.9454 | 0.7698 | 0.1756 |
| DeepSeek | S0 | 0.8898 | 0.7466 | 0.1433 |
| DeepSeek | S2 | 0.8989 | 0.5779 | 0.3210 |
| DeepSeek | S3 | 0.8336 | 0.6718 | 0.1618 |

GPT S3 increases pool coverage by 0.0207 and reduces the gap by 0.0270. Both changes contribute to its final recall gain. The useful pattern combines broader retrieval with better retention.

**S2 on TAR gives GPT and DeepSeek a shared final-selection problem.** Their relevant-pool coverage rises by 0.0058 and 0.0091, respectively. Their official final recall falls by 0.0231 and 0.1686. Both find a broader relevant pool, then retain less evidence in the final output. Only the DeepSeek decline passes the planned adjusted test. Claude also expands its pool, but its final recall rises slightly, by 0.0051.

DeepSeek S2 increases pool coverage by 0.0091, but increases the unretained gap by 0.1777. Its lower final recall therefore comes mainly from what the selected output leaves out. This is an exact arithmetic decomposition of the saved rankings.

A replay holds DeepSeek S2's selected query count fixed and selects the first k distinct queries. Mean TAR recall rises from 0.5780 to 0.7442. The paired change is +0.1662, with interval [+0.0480, +0.2904]. Fusing all distinct queries gives 0.8821. These replays use the stored rankings and make no new search.

The selection effect is conditional. Selecting the first k queries lowers DeepSeek S0 recall. Across all TAR conditions, that rule improves Claude by 0.1063 but lowers GPT by 0.0756. Thus, a fixed early-query rule is not a general replacement for final selection. Query generation and query selection need separate measurement.

**A same-topic example shows the action difference.** CD011515 has the largest observed DeepSeek S2 loss relative to S0. All three S2 sessions select separate MRI, PET, and EUS query groups. GPT reaches recall 1.0, Claude 0.5, and DeepSeek 0.0. Earlier DeepSeek query rankings contain both judged relevant studies. Its final selection includes a title-restricted MRI query at `action_0053`. It also includes an EUS query with `AND NOT "fine-needle"` at `action_0154`. The selected queries retain neither study. This example locates the loss in final query choice; it does not identify one query term as the cause.

The all-query replay covers every shared task. The following means pool S0–S4 equally within each task and model. They use the same official metric and output depth as the selected output.

| Task | Model | Selected-query score | All-query score | Change |
|---|---|---:|---:|---:|
| ToT | GPT | 0.8834 | 0.7478 | -0.1356 |
| ToT | Claude | 0.5941 | 0.4080 | -0.1860 |
| ToT | DeepSeek | 0.6933 | 0.5805 | -0.1128 |
| Genomics | GPT | 0.3468 | 0.3732 | +0.0264 |
| Genomics | Claude | 0.3349 | 0.3471 | +0.0122 |
| Genomics | DeepSeek | 0.3054 | 0.3346 | +0.0292 |
| TAR | GPT | 0.9035 | 0.9369 | +0.0334 |
| TAR | Claude | 0.7797 | 0.9347 | +0.1550 |
| TAR | DeepSeek | 0.6604 | 0.8679 | +0.2075 |

All-query fusion lowers ToT scores and raises TAR recall for all three models. Each paired-topic 95% interval excludes zero. Genomics means also rise, but only the GPT interval excludes zero. Thus, final query selection helps target-film ranking in this replay, while broader query retention helps study coverage. The useful selection rule depends on the task goal.

## RQ3: Effort and score trade-offs

The table shows changes from S0 for S2 and S3. Search and token percentages are ratios of condition means. Total tokens include cached input. They measure recorded effort, not monetary cost.

| Task | Model | S2 score change | S2 searches | S2 tokens | S3 score change | S3 searches | S3 tokens |
|---|---|---:|---:|---:|---:|---:|---:|
| ToT | GPT | +0.0255 | -5.3% | -8.2% | +0.0060 | +7.1% | +0.6% |
| ToT | Claude | -0.0202 | -1.7% | -3.4% | +0.0035 | +9.0% | +11.8% |
| ToT | DeepSeek | +0.0469 | +10.5% | +15.4% | +0.0241 | -2.6% | +1.0% |
| Genomics | GPT | -0.0026 | +13.3% | +34.7% | -0.0333 | +29.1% | +44.4% |
| Genomics | Claude | -0.0313 | +49.2% | +72.0% | +0.0237 | +41.7% | +62.7% |
| Genomics | DeepSeek | -0.0053 | +21.5% | +71.3% | +0.0251 | +7.1% | +28.2% |
| TAR | GPT | -0.0231 | +26.3% | +65.4% | +0.0477 | +36.8% | +69.6% |
| TAR | Claude | +0.0051 | +58.7% | +99.0% | -0.0146 | +26.4% | +42.4% |
| TAR | DeepSeek | -0.1686 | +43.4% | +52.1% | -0.0748 | +8.3% | +8.9% |

DeepSeek S2 has a lower TAR score with more search attempts on 11 of 30 topics. GPT S2 shows that outcome on 12 of 36 Genomics topics; Claude S2 shows it on 17. More work is therefore not evidence of a useful skill.

Later searches often add little to the relevant pool. Consider the final quarter of distinct TAR queries. This quarter adds a new judged relevant study in 7 of 150 GPT sessions. The counts are 13 of 150 for Claude and 21 of 150 for DeepSeek. These searches can still support checking or final selection. The trace records show whether these calls added judged relevant studies to the retrieved pool.

## Shared retrieval baselines

The shared retrieval baselines use the same task data and evaluation. BM25 searches the public request. BM25+RM3 adds pseudo-relevance feedback.

| Task | BM25 | BM25+RM3 |
|---|---:|---:|
| ToT | 0.1078 | 0.0638 |
| Genomics 2007 | 0.1829 | 0.1932 |
| TAR full collection | 0.8083 | 0.7928 |

All three S0 means exceed BM25 on ToT and Genomics. On TAR, Claude S0 and DeepSeek S0 are below BM25. More interaction does not ensure a higher score than fixed retrieval.

## Implications for agentic search

The results show three practical implications. First, evaluate a skill by both its actions and its task score. Shared behavior changes do not guarantee shared quality gains. Second, separate evidence acquisition from final selection. GPT and DeepSeek S2 TAR expand their relevant pools but retain less evidence in the final output. Third, measure effort alongside quality. Additional searches need a task-specific benefit.

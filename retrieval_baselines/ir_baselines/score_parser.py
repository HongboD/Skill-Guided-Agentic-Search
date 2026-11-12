"""Read individual-topic metrics at the official printed precision."""
from collections import defaultdict
import math
PRIMARY_METRICS={'tot2023':'NDCG@1000','genomics2007':'Aspect MAP'}

def parse_official_scores(task, topic_id, stdout):
    """Parse individual-topic output, preserving the official printed precision.

    Genomics ASPECT/MAP over the full gold file includes unsubmitted topics and
    must never stand in for the requested topic's ASPECT score.
    """
    topic_id = str(topic_id)
    if task not in PRIMARY_METRICS:
        raise ValueError('This parser supports ToT 2023 and Genomics 2007.')
    per_topic = defaultdict(dict)
    aggregate = {}
    primary_raw = None
    for line in stdout.splitlines():
        fields = line.split()
        if task == 'genomics2007' and len(fields) == 4:
            _, metric, topic, raw = fields
            if metric not in ('DOCUMENT', 'PASSAGE', 'ASPECT', 'PASSAGE2'):
                continue
        elif task == 'tot2023' and len(fields) == 3:
            metric, topic, raw = fields
        else:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if not math.isfinite(value):
            raise ValueError('Non-finite official score')
        target = aggregate if topic.lower() in ('all', 'map') else per_topic[topic]
        if metric in target and target[metric] != value:
            raise ValueError('Conflicting official metric rows')
        target[metric] = value
        wanted = {'tot2023': 'ndcg_cut_1000', 'genomics2007': 'ASPECT'}[task]
        if topic == topic_id and metric == wanted:
            primary_raw = raw
    if primary_raw is None:
        raise ValueError('Official evaluator did not return the requested topic primary metric')
    return {'primary_metric': PRIMARY_METRICS[task], 'primary_score': float(primary_raw), 'primary_score_as_printed': primary_raw, 'topic_scores': dict(per_topic.get(topic_id, {})), 'aggregate_diagnostics': aggregate, 'aggregate_diagnostics_are_not_the_topic_score': True}

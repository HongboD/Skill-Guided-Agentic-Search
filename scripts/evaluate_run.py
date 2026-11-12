"""Score an existing agent ranking without calling a model or retrieving documents."""
import argparse
import json
from workflow import TASKS, score_ranking


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=TASKS, required=True)
    parser.add_argument('--topic', required=True)
    parser.add_argument('--ranking', required=True)
    parser.add_argument('--qrels', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(score_ranking(args.task, args.topic, args.ranking,
                                  args.qrels, args.output), indent=2))


if __name__ == '__main__':
    main()

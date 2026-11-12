"""Build S0-S4 task prompts locally from externally downloaded topic text."""
import argparse
from pathlib import Path
from workflow import TASKS, CONDITIONS, assemble_prompt, load_topics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=TASKS, required=True)
    parser.add_argument('--topics', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    topics = load_topics(args.topics, args.task)
    args.output.mkdir(parents=True, exist_ok=False)
    for topic in topics:
        folder = args.output / topic['topic_id']
        folder.mkdir()
        for condition in CONDITIONS:
            (folder / (condition + '.txt')).write_text(
                assemble_prompt(args.task, topic, condition), encoding='utf-8')
    print(f'Built {len(topics) * len(CONDITIONS)} prompts in {args.output}')


if __name__ == '__main__':
    main()

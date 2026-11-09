"""Compare shot results with manually confirmed labels; no video is bundled."""
import json
import sys
from pathlib import Path


def evaluate(labels, results, tolerance=1.0):
    unmatched = set(range(len(labels)))
    matched = []
    for shot in results:
        candidates = [(abs(shot['seconds'] - labels[i]['seconds']), i) for i in unmatched]
        if candidates:
            delta, index = min(candidates)
            if delta <= tolerance:
                matched.append((labels[index], shot))
                unmatched.remove(index)
    classified = [(expected, actual) for expected, actual in matched if actual['outcome'] in ('made', 'missed')]
    correct = sum(expected['outcome'] == actual['outcome'] for expected, actual in classified)
    return {'expected_shots': len(labels), 'detected_shots': len(results), 'matched_shots': len(matched),
            'missed_shots': len(labels)-len(matched), 'false_shots': len(results)-len(matched),
            'outcomes_classified': len(classified), 'outcomes_correct': correct,
            'details': [{'expected': e['outcome'], 'actual': a['outcome'], 'seconds': a['seconds']} for e, a in matched]}


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python tests/benchmark_results.py labels.json result.json')
    labels = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    result = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
    print(json.dumps(evaluate(labels['shots'], result['shots']), indent=2))

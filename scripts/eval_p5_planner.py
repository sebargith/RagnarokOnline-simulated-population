"""Run the recorded P5 bench against planner candidates; no game IO.

Cloud candidates receive only the fixture's messages (game facts and
controller-authored intents). A candidate whose API key variable is unset is
reported as unavailable and nothing is sent. Failures are recorded, never retried.
"""
import argparse
import json
from pathlib import Path
import re
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.goal_planner import validate
from inference.m2 import BoundedInference
from inference.openai_compat import KeyUnavailable
from inference.roles import candidate, load_roles

NUMBER = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')


def _numbers(value):
    return {float(n) for n in NUMBER.findall(json.dumps(value))}


def score(case, content):
    """json/capability/fact flags; None means not applicable."""
    out = {'json': False, 'capability': False, 'fact': False}
    try:
        value = json.loads(content)
    except (TypeError, ValueError):
        return out
    if case['kind'] == 'goal':
        try:
            value = validate(value)
        except (ValueError, TypeError, KeyError):
            return out
        out['json'] = True
        maximum = case['response_format']['properties']['additional_kills']['maximum']
        out['capability'] = value['type'] in case['allowed'] and value['additional_kills'] <= maximum
        out['fact'] = out['capability'] and value['type'] in case['expected']
    elif case['kind'] == 'mechanics':
        out['json'] = isinstance(value, dict) and set(value) == {'topic'} and isinstance(value['topic'], str)
        out['capability'] = out['json'] and value['topic'] in case['allowed']
        out['fact'] = out['capability'] and value['topic'] in case['expected']
    else:
        summary = value.get('summary') if isinstance(value, dict) and set(value) == {'summary'} else None
        out['json'] = isinstance(summary, str) and bool(summary.strip())
        if out['json']:
            facts = case['facts']
            allowed = _numbers(facts) | {round(100*facts['base_exp']/facts['base_exp_needed']),
                                         round(100*facts['job_exp']/facts['job_exp_needed']),
                                         round(100*facts['hp']/facts['hp_max'])}
            invented = sorted(n for n in (float(x) for x in NUMBER.findall(summary)) if n not in allowed)
            out['capability'] = not invented  # grounded: no number outside the facts
            out['invented_numbers'] = invented
            text = summary.casefold()
            missing = [r for r in case['required'] if
                       (str(r).casefold() not in text if isinstance(r, str)
                        else not re.search(r'(?<!\d)%d(?!\d)' % r, text))]
            out['fact'] = not missing
            out['missing_facts'] = missing
    return out


def percent(rows, key):
    return round(100*sum(bool(r['score'][key]) for r in rows)/len(rows)) if rows else None


def summarize(rows):
    latencies = sorted(r['response_s'] for r in rows if r.get('response_s') is not None and not r.get('error'))
    return {'calls': len(rows), 'json_pct': percent(rows, 'json'), 'capability_pct': percent(rows, 'capability'),
            'fact_pct': percent(rows, 'fact'), 'errors': sum(bool(r.get('error')) for r in rows),
            'p50_s': round(statistics.median(latencies), 2) if latencies else None,
            'max_s': round(latencies[-1], 2) if latencies else None}


def run_candidate(doc, name, cases, repeats):
    try:
        config, model, transport = candidate(doc, name)
    except KeyUnavailable as error:
        return {'status': 'unavailable', 'reason': str(error), 'rows': []}
    service = BoundedInference(config, model, transport)
    rows, first = [], True
    try:
        for repeat in range(repeats):
            for case in cases:
                future = service.submit(f"{case['id']}-{repeat}", case['messages'], case['seed'],
                                        cold=first or case['cold'], response_format=case['response_format'])
                limit = config['cold_request_deadline_s'] + 10
                result = future.result(limit)
                first = False
                row = {'case': case['id'], 'kind': case['kind'], 'repeat': repeat,
                       'response_s': round(result.get('response_s', 0), 3), 'error': result.get('error')}
                for key in ('eval_count', 'thinking_chars', 'reasoning_tokens', 'served_model'):
                    if result.get(key) is not None:
                        row[key] = result[key]
                row['content'] = (result.get('content') or '')[:1500]
                row['score'] = score(case, result.get('content'))
                rows.append(row)
                print(json.dumps({'candidate': name, 'case': case['id'], 'repeat': repeat,
                                  'response_s': row['response_s'], 'error': row['error'],
                                  'score': row['score']}), flush=True)
                if row['error']:
                    time.sleep(2)
                    # Explicit, recorded reset so later cases are still measured.
                    row['circuit_reset'] = service.recover_idle_circuit()
    finally:
        service.close()
    return {'status': 'ran', 'model': model, 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', default='qwen9b-current,qwen9b-tuned,gemini-flash,groq-gpt-oss')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--bench', type=Path, default=ROOT/'fixtures/p5-planner-bench.json')
    parser.add_argument('--out', type=Path, default=ROOT/'docs/evidence/P5-model-eval-results.json')
    args = parser.parse_args()
    doc = load_roles()
    bench = json.loads(args.bench.read_text(encoding='utf-8'))
    previous = json.loads(args.out.read_text(encoding='utf-8')) if args.out.exists() else {'candidates': {}}
    for name in args.candidates.split(','):
        started = time.time()
        result = run_candidate(doc, name, bench['cases'], args.repeats)
        result['started_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started))
        result['summary'] = summarize(result['rows'])
        result['by_kind'] = {kind: summarize([r for r in result['rows'] if r['kind'] == kind])
                             for kind in ('goal', 'report', 'mechanics')}
        previous['candidates'][name] = result
        args.out.write_text(json.dumps(previous, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        print(json.dumps({'candidate': name, 'status': result['status'], 'summary': result['summary'],
                          'reason': result.get('reason')}), flush=True)


if __name__ == '__main__':
    main()

"""Capture one real public GitHub response for offline regression, not an MVP run."""
from .core import Client, parse_github, write_json

URL = 'https://github.com/search?q=ai+agent&type=repositories'


def main():
    client = Client('tests/fixtures/public_capture')
    body, meta = client.get(URL, 'github_sample')
    try:
        repos = parse_github(body)
        if len(repos) < 5:
            raise ValueError('public sample must contain at least five repositories')
        client.log('validation_pass', adapter='github', extracted_count=len(repos))
    except Exception as exc:
        client.log('validation_fail', adapter='github', error=str(exc))
        raise
    write_json('tests/fixtures/public_capture/sample_index.json', {
        'purpose': 'real public request captured for offline parser regression; not historical evidence',
        'response': meta, 'expected_repo_ids': [item['source_id'] for item in repos]})
    print('Captured public sample:', len(repos), 'repositories;', meta['sha256'])


if __name__ == '__main__':
    main()

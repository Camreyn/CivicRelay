"""Fixed local installer bridge. No mail modules, private stores or supplied paths."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'app'))
from updates import Updates, UpdateError

if __name__ == '__main__':
    try:
        updater = Updates(ROOT)
        command = sys.argv[1] if len(sys.argv) == 2 else ''
        if command == 'describe':
            approval, destination = updater.approved()
            print(json.dumps({'version': approval['release']['version'], 'destination': str(destination), 'stage': approval['stage']}))
        elif command == 'extract':
            with updater.exclusive():
                print(updater.extract())
        elif command in ('installed', 'failed'):
            with updater.exclusive():
                updater.finish(command)
        else:
            raise UpdateError('Unknown update installer command.')
    except Exception as error:
        print(str(error) if isinstance(error, UpdateError) else 'The local updater stopped safely. No private diagnostics were exposed.', file=sys.stderr)
        sys.exit(1)

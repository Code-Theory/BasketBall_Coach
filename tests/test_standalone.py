"""Copy only deployable files and exercise detection from the relocated copy.

The source virtual environment supplies the application interpreter for this test;
setup.bat must create a fresh application environment on a destination machine.
"""
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python tests/test_standalone.py path/to/sample_video.mp4')
    video = Path(sys.argv[1]).resolve()
    copy = root / 'data' / ('standalone-check-' + uuid.uuid4().hex)
    copy.mkdir()
    try:
        for filename in ('app.py', 'analysis.py', 'shot_logic.py', 'hoop_worker.py', 'hoop_tracker.py', 'tracker_bridge.py'):
            shutil.copy2(root / filename, copy / filename)
        for directory in ('templates', 'static', 'tests', 'runtime', 'vendor'):
            shutil.copytree(root / directory, copy / directory, ignore=shutil.ignore_patterns('__pycache__'))
        (copy / 'models').mkdir()
        for filename in ('hoop_detector.pb', 'yolov8s.onnx', 'yolov8n.onnx', 'pose_landmarker_lite.task'):
            shutil.copy2(root / 'models' / filename, copy / 'models' / filename)
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        check = subprocess.run([sys.executable, '-c',
            "from app import ROOT, HOOP_PYTHON, HOOP_GRAPH; "
            "assert HOOP_PYTHON.is_file() and HOOP_GRAPH.is_file(); "
            "assert HOOP_PYTHON.is_relative_to(ROOT) and HOOP_GRAPH.is_relative_to(ROOT); print(ROOT)"],
            cwd=copy, env=env, text=True, capture_output=True, timeout=30)
        assert check.returncode == 0, check.stdout + check.stderr
        print('Relocated project:', check.stdout.strip(), flush=True)
        result = subprocess.run([sys.executable, 'tests/smoke_sample.py', str(video)],
                                cwd=copy, env=env, text=True, capture_output=True,
                                encoding='utf-8', errors='replace', timeout=240)
        assert result.returncode == 0, result.stdout + result.stderr
        print('Standalone upload, hoop detection, and analysis passed.', flush=True)

    finally:
        shutil.rmtree(copy)


if __name__ == "__main__":
    main()

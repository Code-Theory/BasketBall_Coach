# CourtVision

**CourtVision is a local basketball practice analysis application that turns a shooting session into a reviewable film room.** It combines basketball detection, shot tracking, and pose estimation to help players inspect attempts, review estimated outcomes, and study movement around a shot.

The application runs on your computer and does not require an API key, a cloud service, or custom model training. Automatic results are estimates and should be checked against the footage.

## Features

- **Shot tracking:** identifies possible attempts and estimates made, missed, or uncertain outcomes.
- **Form study:** displays estimated load, release, and follow-through frames with pose landmarks and 2D knee and elbow measurements.
- **Shot review:** seek to an attempt or rim crossing, adjust playback speed, correct an outcome, remove a false detection, or add a missed attempt.
- **Evidence indicators:** flags low-evidence trajectory estimates for review and distinguishes automatic results from manually reviewed outcomes.
- **Session report:** downloads a standalone HTML report containing shot review, selected form frames, and observations. Reviewed shooting percentage uses only manually reviewed outcomes.
- **Illustrative demo:** explores the interface using simulated footage and example measurements.
- **Local processing:** analysis and review data stay on the machine running the application.

## System requirements

| Component | Requirement |
| --- | --- |
| Operating system | 64-bit Windows. The included automatic hoop-detection runtime is Windows-specific. |
| Python | Python 3.12, 64-bit, with the Windows `py` launcher. |
| Browser | A current desktop browser with JavaScript enabled; Chrome or Edge is recommended. |
| Hardware | CPU execution is supported. Processing time depends on the computer and recording; 8 GB RAM or more is recommended. |
| Storage | Space for the included models and runtime, Python environment, local uploads, and results. Longer recordings require additional space. |
| Internet | Required during initial dependency installation; normal analysis runs locally after setup. |
| GPU | Not required. The default installation uses ONNX Runtime's CPU package. |

Keep the `models/` and `runtime/hoop-python36/` folders alongside the application. These contain assets used by the analysis pipeline and automatic hoop detection. The application is configured for a local, single-user Windows setup; Linux, macOS, and public hosting have not been verified.

## Getting started

1. Install **64-bit Python 3.12** and ensure the Python launcher is available.
2. In the CourtVision folder, run `setup.bat`. This creates `.venv` and installs the Python dependencies in `requirements.txt`.
3. Run `start.bat` and keep its window open while using the application.
4. Open **http://127.0.0.1:5050** in your browser.

If setup reports that Python is missing, check the installation with:

```powershell
py -3.12-64 --version
```

When moving the project to another computer, create a fresh virtual environment with `setup.bat`; do not rely on a copied `.venv`.

## Analyze a practice session

1. Select a supported recording. The upload limit is **200 MB**; MP4, MOV, M4V, and AVI are accepted.
2. Check the suggested hoop selection. Draw a box around the **rim opening**, not the entire net, if the suggestion needs adjustment. If automatic hoop detection is unavailable, select the rim manually.
3. Start the analysis and wait for processing to finish.
4. Select an attempt in the shot timeline. Replay it, review the rim crossing when available, and correct or confirm the outcome.
5. Inspect the form frames and download the session report if needed.

For best results, use a steady camera with one player, the ball, and the hoop in view. Keep the full body visible and use adequate lighting. A closer, unobstructed view of the rim improves the chance of following the ball through the basket. Several players or balls, fast camera movement, occlusion, or an out-of-frame ball can produce incorrect or missing detections.

## How it works

1. **Detection:** a basketball-specific YOLO model identifies ball candidates in sampled frames. MediaPipe Pose Landmarker estimates body landmarks.
2. **Tracking:** CourtVision passes ball detections and the selected rim position to its integration of Basketball Shot Tracker.
3. **Shot analysis:** the application matches tracker events to possible releases and collects estimated load, release, and follow-through measurements.
4. **Review:** results are shown alongside the recording. You can correct outcomes and save a report.

The default ball detector is the included Swish-Vision ONNX model. CourtVision falls back to YOLOv8s if that model is missing. For an explicit model selection, set `COURTVISION_BALL_MODEL` to `swish`, `standard`, or `fast` before starting the application.

## Understanding the results

Shot counts and outcomes can be incorrect. A ball passing behind or in front of the rim can appear to cross it in a 2D image, and the ball may be hidden by the net or backboard. The tracker may use a fitted or extrapolated path; those results are labeled **low-evidence** and included in the review count. An uncertain result means the app could not make a supported call.

Knee and elbow values are **2D image measurements**, not validated biomechanical assessments. Perspective, landmark visibility, and estimated phase timing affect them. Coaching cues are prompts for further review; they do not establish why a shot was missed. Manually added attempts do not have automatic form measurements.

One locally held, manually labeled four-shot practice recording was tested with the current tracker integration and a manually selected first-frame rim. All four attempts and outcomes matched the labels; three outcome calls used low-evidence extrapolation. This small test does not establish performance on other recordings.

## Data and privacy

Uploads, generated analysis images, results, and review corrections are stored under `data/`. They remain on the local machine until removed. The most recent completed review is restored in the same browser when available; the illustrative demo is temporary. `data/`, local virtual environments, logs, and common recording formats are excluded by `.gitignore`.

## Running checks

Run the automated unit and integration tests from the project folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

The end-to-end smoke test accepts a local sample file:

```powershell
.\.venv\Scripts\python.exe tests\smoke_sample.py "C:\path\to\sample.mp4"
```

The smoke test's automatic hoop-selection assertions are calibrated for the original project sample and may not pass for an unrelated recording.

## Project structure

```text
CourtVision/
├── app.py                 # Flask routes, job state, and review persistence
├── analysis.py            # Video analysis, pose metrics, and ball detection
├── shot_logic.py          # Release recognition and shot observations
├── tracker_bridge.py      # Adapter for the bundled shot tracker
├── hoop_tracker.py        # Rim-position tracking
├── hoop_worker.py         # Automatic hoop-detection worker
├── models/                # Detection and pose model assets
├── runtime/               # Windows hoop-detection runtime
├── vendor/shottracker/    # Bundled tracker source and notices
├── templates/             # Application markup
├── static/                # Interface styles and client-side behavior
├── tests/                 # Unit, integration, and smoke tests
├── requirements.txt       # Python dependencies
├── setup.bat              # Windows setup
└── start.bat              # Local application launcher
```

## Credits and licensing

CourtVision uses [MediaPipe Pose Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker), a basketball detector derived from [Swish-Vision](https://github.com/ahmedsilat44/Swish-Vision), ONNX Runtime, OpenCV, and Flask. Shot tracking and judging incorporate [Basketball Shot Tracker](https://github.com/NathanielRecto/Basketball-Shot-Tracker), snapshot `88ac29684a5843f4eccc4e067f23c5c5da69e38b`. Its AGPL-3.0-or-later license and third-party notices are included in `vendor/shottracker/`.

Review the licenses and redistribution terms of all dependencies and model weights before distributing the application or offering it as a network service. The origins or separate redistribution terms of some included weights, including the hoop detector and Swish-Vision-derived weights, have not been independently verified.

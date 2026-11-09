# CourtVision

CourtVision analyzes a basketball practice video locally using pretrained MediaPipe Pose Landmarker Lite and YOLOv8s. No training or API key is needed.

## Start

On 64-bit Windows, install Python 3.12 and double-click `setup.bat` once to create the application environment and install its dependencies. Then double-click `start.bat` and open http://127.0.0.1:5050. Keep `models/` and `runtime/hoop-python36/` alongside the application. You do not need either neighboring project.

Upload a short video. The app searches for the hoop and shows a suggested box; check that it surrounds the **rim opening** and drag a replacement if needed. A stationary camera with one player, the full body, ball and rim visible gives the best chance of detection. You can skip the rim selection, but automatic outcomes will be uncertain. Processing happens on your computer; uploaded files and results remain under `data/` until removed.

The results show estimated releases across the clip, made/missed/uncertain outcomes, and form measurements for a selected shot. Play the video to review the results. You can change outcomes, remove false detections, and add attempts at the current video time. These corrections live in the page and are lost when it is closed or reloaded; manually added shots do not have automatic form measurements.

## Limits

- The current detector is a general-purpose sports-ball model, not a basketball-specific model. Small, fast or hidden balls and obstructed players may cause missed or false shots. A displayed count of zero does not prove that there were no shots.
- Automatic hoop detection uses the included Windows x64 runtime and hoop graph. If either is missing or detection fails, draw the hoop manually. The detector includes the net, so the suggested opening is approximated from the upper part of its box and must be checked. An outcome is estimated only when a detected ball path crosses near the marked rim; ball disappearance and other incomplete paths remain uncertain. A 2D crossing cannot establish depth or guarantee a make. Review and correct the video results.
- Knee and elbow angles are 2D estimates, affected by camera perspective and landmark visibility. The apparent ball angle is measured in the image and is not necessarily the true 3D release angle. Flags such as a nearly straight knee or flat image trajectory are simple review cues, not proven causes of a miss.
- Analysis samples roughly 12 frames per second. Closely spaced shots, dribbles, layups, occlusions, multiple players, camera movement, or a ball outside the frame can lead to mistakes. Performance is not validated across diverse real-world clips.
- Use one analysis at a time. The app processes on CPU by default; processing time depends on the hardware and clip length. For faster but potentially less accurate ball detection, set `COURTVISION_BALL_MODEL=fast` before launching to use the included YOLOv8n model.

The included models are [Google MediaPipe Pose Landmarker Lite](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task) and the included ONNX export of Ultralytics YOLOv8s (its embedded metadata identifies an AGPL-3.0 license; the original export source has not been verified). Check the upstream model and dependency licenses before redistribution or commercial use. The older local OpenPose project is not needed to run CourtVision.

## Verification

Run `.venv\Scripts\python.exe -m unittest discover -s tests -p test_shot_logic.py` for synthetic event tests. Run `.venv\Scripts\python.exe tests\smoke_sample.py "path\to\sample_video.mp4"` for the upload-to-results test. The smoke test's rim box is calibrated for the sample video from the older AI Basketball Analysis project.

The bundled hoop graph was sourced from the AI Basketball Analysis project. The origin and licensing of its trained weights have not been independently verified; review them before redistribution. The neighboring project also includes OpenPose with a noncommercial research license, but OpenPose is not used by CourtVision.

## Moving or deploying

Copy the CourtVision folder, including `models/` and `runtime/`, to a 64-bit Windows machine. Do not rely on a copied `.venv`: Python virtual environments contain machine-specific paths. Install Python 3.12, run `setup.bat` once (internet access is needed to install dependencies), then run `start.bat`. The embedded hoop runtime works independently of other project folders. `data/` contains uploads and generated images; omit it when packaging if those files should not be included.

This package has been prepared for 64-bit Windows. Its bundled hoop runtime is Windows-specific; Linux, macOS and public internet hosting are not configured or tested. The Flask server binds to localhost and is intended for a single user, not production hosting. The bundled runtime contains older Python and TensorFlow versions; isolate it appropriately and review dependency and model licenses before distributing the package.

## Basketball Shot Tracker integration

CourtVision bundles the source of [Basketball Shot Tracker](https://github.com/NathanielRecto/Basketball-Shot-Tracker) under `vendor/shottracker/` (snapshot `88ac29684a5843f4eccc4e067f23c5c5da69e38b`), together with its AGPL-3.0 license and third-party notices. CourtVision adapts detections from its existing general-purpose YOLO model to the vendored ball tracker and shot judge, and matches judged events to detected releases. The upstream repository does not distribute its basketball-specific detector weights, so its published accuracy figures do not apply to this integration. Unmatched releases and extrapolated-only outcomes remain uncertain and can be reviewed in the video. The tracker runs on the existing sampled frames; in the four-shot practice clip, ball detections remain too sparse around the rim for reliable automatic outcomes. No training is required.

The bundled tracker code is AGPL-3.0-or-later. The hoop detector weights' origin and redistribution terms remain unverified; review all model and dependency licenses before distributing CourtVision or deploying it as a network service.

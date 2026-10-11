# LabelOps local prototype

LabelOps is a local demo of an end-to-end medical-device labeling workflow. It includes change-request intake, local artwork comparison, optional OpenAI-compatible LLM review triage, label records, a sample verification checklist, and an audit view.

## Run it

1. Install Python 3.10 or newer.
2. On Windows, double-click `Start-LabelOps.bat`; it installs missing dependencies automatically. You can also run `setup.bat` once first. On macOS/Linux, run `python -m pip install -r requirements.txt`.
3. (Optional) Copy `.env.example` to `.env` and set `LLM_API_KEY`. `LLM_BASE_URL` and `LLM_MODEL` can point to another OpenAI-compatible chat-completions service. Keep `.env` private; it is ignored from version control.
4. Run `python server.py` on macOS/Linux, or double-click `Start-LabelOps.bat` on Windows. `run.ps1` is also available for PowerShell.
5. Open http://127.0.0.1:8765.

The interface works in rules-only mode when there is no LLM key. OpenCV is used if installed; if not, the included Pillow fallback compares images and highlights a bounding region. `requirements.txt` includes OpenCV for the full computer-vision path.

## Artwork comparison

Upload the released baseline and the proposed revision as PNG, JPEG or WEBP. The server computes a pixel-difference mask, highlights candidate regions, and reports a visual-difference percentage. It aligns the revised image to the baseline dimensions for screening if sizes differ, and calls that out in the result. This is not OCR, a regulatory rules engine, or a validated image inspection system.

When `LLM_API_KEY` is configured, the app sends comparison filenames, dimensions, difference percentage, region coordinates and screening notes to the configured chat-completions endpoint. It does not send image pixels to the LLM. The LLM returns advisory triage only and cannot approve or release a label. Treat the endpoint according to your data-handling requirements.

## Data and limits

- Change requests, comparison metadata and audit events are stored in `work/labelops-data.json`.
- Uploaded image bytes are processed in memory and are not saved as source files by this prototype.
- Files are limited to 18 MB each and 28 megapixels.
- The demo has no authentication, role-based access, database encryption, validated e-signature, retention controls, live regulatory feeds, or production system integration.
- Seeded labels, requirements and product details are examples. Verify all information against approved sources. A qualified Regulatory Affairs and Quality review remains mandatory.

Do not use this prototype to make production-release decisions or process confidential artwork unless the local environment and configured LLM provider are approved for that data.

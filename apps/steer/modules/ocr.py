"""OCR using Tesseract on Linux."""

from dataclasses import dataclass

from modules.errors import SteerError
from modules.tools import require


@dataclass
class OCRResult:
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


def recognize(image_path: str, minimum_confidence: float = 0.5) -> list[OCRResult]:
    """Run OCR on an image file using Tesseract.

    Returns list of recognized text regions with bounding boxes.
    """
    require("tesseract")
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise SteerError("pytesseract or Pillow not installed")

    img = Image.open(image_path)
    # Get word-level bounding boxes with confidence
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    results = []
    n_boxes = len(data["text"])

    # Group consecutive words on the same line into text regions
    current_text = []
    current_box = None
    current_conf = []

    for i in range(n_boxes):
        text = data["text"][i].strip()
        conf = float(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.0

        if not text:
            # End of a text region - save accumulated
            if current_text and current_box:
                avg_conf = sum(current_conf) / len(current_conf)
                if avg_conf >= minimum_confidence:
                    results.append(OCRResult(
                        text=" ".join(current_text),
                        confidence=round(avg_conf, 2),
                        x=current_box[0],
                        y=current_box[1],
                        width=current_box[2],
                        height=current_box[3],
                    ))
            current_text = []
            current_box = None
            current_conf = []
            continue

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        if current_box is None:
            current_box = [x, y, w, h]
            current_text = [text]
            current_conf = [conf]
        else:
            # Check if same line (similar y position)
            if abs(y - current_box[1]) < current_box[3] * 0.5:
                # Extend bounding box
                new_right = max(current_box[0] + current_box[2], x + w)
                current_box[2] = new_right - current_box[0]
                current_box[3] = max(current_box[3], h)
                current_text.append(text)
                current_conf.append(conf)
            else:
                # New line - save current and start new
                avg_conf = sum(current_conf) / len(current_conf)
                if avg_conf >= minimum_confidence:
                    results.append(OCRResult(
                        text=" ".join(current_text),
                        confidence=round(avg_conf, 2),
                        x=current_box[0],
                        y=current_box[1],
                        width=current_box[2],
                        height=current_box[3],
                    ))
                current_box = [x, y, w, h]
                current_text = [text]
                current_conf = [conf]

    # Don't forget the last region
    if current_text and current_box:
        avg_conf = sum(current_conf) / len(current_conf)
        if avg_conf >= minimum_confidence:
            results.append(OCRResult(
                text=" ".join(current_text),
                confidence=round(avg_conf, 2),
                x=current_box[0],
                y=current_box[1],
                width=current_box[2],
                height=current_box[3],
            ))

    return results


def to_elements(results: list[OCRResult]) -> list[dict]:
    """Convert OCR results to UI element dicts compatible with ElementStore."""
    elements = []
    for i, r in enumerate(results):
        elements.append({
            "id": f"O{i + 1}",
            "role": "ocrtext",
            "label": r.text,
            "value": None,
            "x": r.x,
            "y": r.y,
            "width": r.width,
            "height": r.height,
            "isEnabled": True,
            "depth": 0,
        })
    return elements

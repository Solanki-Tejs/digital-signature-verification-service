import cv2
import numpy as np
from PIL import Image
import albumentations as A
import os


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
TARGET_SIZE = 224
NORM_MEAN = [0.485, 0.456, 0.406]   # ImageNet mean (pretrained ResNet)
NORM_STD  = [0.229, 0.224, 0.225]   # ImageNet std


# ─────────────────────────────────────────────
# CORE PREPROCESSING FUNCTION
# ─────────────────────────────────────────────
def preprocess_signature(image_input, augment=False):
    """
    Full preprocessing pipeline for a signature image.

    Args:
        image_input : str (file path) OR numpy array OR PIL Image
        augment     : bool — apply augmentation (True during training only)

    Returns:
        tensor : numpy array of shape (3, 224, 224), float32, normalized
        visual : numpy array (224, 224, 3) uint8 — for display/debugging
    """

    # ── Step 1: Load image ──────────────────────────────────────
    img = _load_image(image_input)

    # ── Step 2: Convert to Grayscale ────────────────────────────
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── Step 3: Remove horizontal ruled lines ───────────────────
    #    Fixes: ruled paper / cheque lines bleeding into signature
    # no_lines = _remove_lines(gray)

    # ── Step 4: Remove background noise (Otsu thresholding) ─────
    cleaned = _remove_background(gray)

    # ── Step 5: Crop to signature bounding box ──────────────────
    #    Fixes: excess black space around signature
    # cropped = _crop_to_signature(cleaned)

    # ── Step 6: Smart Resize to 224x224 ─────────────────────────
    #    Small images (e.g. 28x28): INTER_CUBIC  (smoother upscale)
    #    Large images             : INTER_AREA   (sharper downscale)
    resized = _smart_resize(cleaned, TARGET_SIZE)

    # ── Step 7: Grayscale → RGB (ResNet needs 3 channels) ───────
    rgb = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)

    # Save visual copy before normalization
    visual = rgb.copy()

    # ── Step 8: Augmentation (training only) ────────────────────
    if augment:
        rgb = _augment(rgb)

    # ── Step 9: Normalize (ImageNet stats) ──────────────────────
    tensor = _normalize(rgb)

    return tensor, visual


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def _load_image(image_input):
    """Accept file path, numpy array, or PIL Image."""
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
        if img is None:
            raise ValueError(f"Could not read image at: {image_input}")
    elif isinstance(image_input, np.ndarray):
        img = image_input.copy()
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif isinstance(image_input, Image.Image):
        img = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
    else:
        raise TypeError(f"Unsupported image type: {type(image_input)}")
    return img


def _remove_lines(gray):
    """
    Detects and removes horizontal ruled lines (from paper/cheques).
    Uses morphological opening with a wide horizontal kernel to isolate
    long horizontal lines, then subtracts them from the image.
    """
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detected_lines    = cv2.morphologyEx(gray, cv2.MORPH_OPEN,
                                          horizontal_kernel, iterations=2)
    no_lines = cv2.subtract(gray, detected_lines)
    return no_lines


def _remove_background(gray):
    """
    Otsu thresholding — isolates signature strokes from background.
    Strokes = white, background = black after inversion.
    """
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Remove tiny noise specks
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return cleaned


def _crop_to_signature(binary):
    """
    Crops tightly around the signature strokes, removing excess black space.
    Adds small padding so strokes aren't cut off at edges.
    Falls back to original if no strokes found.
    """
    coords = cv2.findNonZero(binary)
    if coords is None:
        return binary   # no strokes found, return as-is

    x, y, w, h = cv2.boundingRect(coords)

    # Add padding around signature so strokes aren't clipped
    padding = 10
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(binary.shape[1] - x, w + 2 * padding)
    h = min(binary.shape[0] - y, h + 2 * padding)

    return binary[y:y+h, x:x+w]


def _smart_resize(gray, target):
    """
    Resize with correct interpolation based on original vs target size.
    Upscaling  (28x28   → 224x224): INTER_CUBIC — adds smooth pixels
    Downscaling(512x512 → 224x224): INTER_AREA  — best for shrinking
    """
    h, w   = gray.shape[:2]
    interp = cv2.INTER_CUBIC if (h < target or w < target) else cv2.INTER_AREA
    return cv2.resize(gray, (target, target), interpolation=interp)


def _augment(rgb):
    """
    Light augmentation for training.
    NO horizontal/vertical flips — a flipped signature looks forged!
    """
    transform = A.Compose([
        A.Rotate(limit=5, p=0.5),                                        # slight tilt
        A.GaussNoise(noise_scale_factor=0.1, p=0.3),                     # scanner noise
        A.RandomBrightnessContrast(brightness_limit=0.1,
                                   contrast_limit=0.1, p=0.3),           # ink variation
        A.ElasticTransform(alpha=1, sigma=10, p=0.2),                    # pen pressure
    ])
    return transform(image=rgb)["image"]


def _normalize(rgb):
    """
    Normalize using ImageNet stats.
    Returns (3, H, W) float32 array — ready to feed into ResNet.
    """
    img        = rgb.astype(np.float32) / 255.0
    mean       = np.array(NORM_MEAN, dtype=np.float32)
    std        = np.array(NORM_STD,  dtype=np.float32)
    normalized = (img - mean) / std
    # HWC → CHW  (channels last → channels first)
    return np.transpose(normalized, (2, 0, 1)).astype(np.float32)


# ─────────────────────────────────────────────
# BATCH PROCESSING (for training dataset)
# ─────────────────────────────────────────────

def preprocess_dataset(input_dir, output_dir, augment=False):
    """
    Process entire dataset folder and save tensors as .npy files.

    Expected folder structure:
        input_dir/
            001/          genuine images
            001_forg/     forged images
            002/
            002_forg/
    """
    os.makedirs(output_dir, exist_ok=True)
    stats = {"processed": 0, "failed": 0}

    all_folders = os.listdir(input_dir)
    user_ids    = sorted([
        f for f in all_folders
        if os.path.isdir(os.path.join(input_dir, f)) and not f.endswith("_forg")
    ])

    for uid in user_ids:
        for suffix, label in [("", "genuine"), ("_forg", "forged")]:
            folder   = os.path.join(input_dir, f"{uid}{suffix}")
            out_path = os.path.join(output_dir, uid, label)
            if not os.path.exists(folder):
                continue
            os.makedirs(out_path, exist_ok=True)
            for fname in os.listdir(folder):
                if not fname.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif")):
                    continue
                try:
                    fpath     = os.path.join(folder, fname)
                    tensor, _ = preprocess_signature(fpath, augment=augment)
                    save_name = fname.rsplit(".", 1)[0] + ".npy"
                    np.save(os.path.join(out_path, save_name), tensor)
                    stats["processed"] += 1
                except Exception as e:
                    print(f"  WARNING: Failed {fname} — {e}")
                    stats["failed"] += 1

    print(f"\nDone! Processed: {stats['processed']}  Failed: {stats['failed']}")
    return stats


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("TEST 1: 28x28 tiny image (simulating small input)")
    print("=" * 55)
    tiny = np.full((28, 28, 3), 240, dtype=np.uint8)
    cv2.line(tiny, (2, 14), (26, 14), (30, 30, 30), 2)
    cv2.line(tiny, (10, 5), (18, 23), (30, 30, 30), 1)
    tensor1, visual1 = preprocess_signature(tiny, augment=False)
    print(f"\n  Tensor shape : {tensor1.shape}")
    print(f"  Value range  : [{tensor1.min():.3f}, {tensor1.max():.3f}]")

    print("\n" + "=" * 55)
    print("TEST 2: 512x512 image with ruled lines + augmentation ON")
    print("=" * 55)
    large = np.full((512, 512, 3), 245, dtype=np.uint8)
    # Simulate ruled lines
    for y in range(100, 450, 50):
        cv2.line(large, (0, y), (512, y), (180, 180, 180), 1)
    # Simulate signature strokes
    cv2.line(large, (50, 256), (462, 256), (20, 20, 20), 5)
    cv2.ellipse(large, (256, 200), (100, 60), 0, 0, 360, (20, 20, 20), 3)
    tensor2, visual2 = preprocess_signature(large, augment=True)
    print(f"\n  Tensor shape : {tensor2.shape}")
    print(f"  Value range  : [{tensor2.min():.3f}, {tensor2.max():.3f}]")

    print("\n✅ Preprocessing pipeline working correctly!")
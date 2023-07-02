from PIL import Image
from psd_tools import PSDImage
import os


def load_image_from_file(path: str, additional_types: tuple):
    if os.path.exists(path) and os.path.isfile(path):
        if path.endswith(".psd"):
            psd_image = PSDImage.open(path).composite()
            if not hasattr(psd_image, "filename"):
                psd_image.filename = path
            return psd_image
        if path.endswith(additional_types):
            return Image.open(path)
    return Image.new("RGB", (0, 0))


def get_image(img, types: tuple | None = (".png", ".jpg", ".jpeg", ".webp")):
    if type(img) == str:
        return load_image_from_file(img, types)
    elif type(img) == Image.Image:
        return img
    error = Image.new("RGB", (0, 0))
    return error

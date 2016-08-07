""" Basic operations on images. """

from PIL import Image
import numpy as np


def load_image(fn, grayscale):
    pic = Image.open(fn)
    if grayscale:
        pic = pic.convert("L")
    return np.array(pic)


def save_image(img, fn):
    pic = Image.fromarray(img)
    pic.save(fn)


def get_pixel(img, x, y, block=1):
    def safe_get(arr, j, i):
        if j < 0 or j >= arr.shape[1]:
            return None
        if i < 0 or i >= arr.shape[0]:
            return None
        return int(arr[i, j])

    if block == 1:
        return safe_get(img, x, y)

    pixel = None
    r = block / 2
    l = block - r - 1
    for py in xrange(y - l, y + r + 1):
        for px in xrange(x - l, x + r + 1):
            p = safe_get(img, px, py)
            if p is None:
                continue
            if pixel is None:
                pixel = p
            else:
                pixel += p
    if pixel is not None:
        pixel /= block * block
    return pixel


def rgb_to_gray(rgb):
    red = float(rgb[0])
    green = float(rgb[1])
    blue = float(rgb[2])
    gray = (red * 0.299) + (green * 0.587) + (blue * 0.114)
    return np.uint8(gray)


def diff(img1, img2):
    """ Difference between two RGB 24-bit images. """
    d = img1.astype(np.int32) - img2.astype(np.int32)
    d[:, :, 0] -= d[:, :, 0].min()
    d[:, :, 1] -= d[:, :, 1].min()
    d[:, :, 2] -= d[:, :, 2].min()
    return d.astype(np.uint8)

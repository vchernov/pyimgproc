""" Computation of Local Binary Patterns. """

import math

import numpy as np
from matplotlib import pyplot as plt

import imgop


def lbp(img, x, y, radius=1, points=8, block=1):
    """ Computes Local Binary Pattern. """

    center = imgop.get_pixel(img, x, y, block)

    pattern = 0
    for p in xrange(0, points):
        angle = 2.0 * math.pi * p / points
        px = x + int(round(radius * math.cos(angle)))
        py = y - int(round(radius * math.sin(angle)))

        pixel = imgop.get_pixel(img, px, py, block)
        if pixel is None:
            continue

        if pixel >= center:
            pattern += 2 ** p

    return get_rotation_inv(pattern, points)


def feature(img, distrib, step=1, radius=1, points=8, block=1):
    """ Computes feature vector based on occurrence histogram of Local Binary Patterns. """

    histogram = np.zeros(len(distrib) + 1, dtype=int)

    processed = 0
    for y in xrange(0, img.shape[0], step):
        for x in xrange(0, img.shape[1], step):
            pattern = lbp(img, x, y, radius, points, block)

            index = distrib.get(pattern, points + 1)
            cnt = histogram[index] + 1
            histogram[index] = cnt

            processed += 1
            if processed % 50000 == 0:
                print "%d pixels processed" % processed

    return histogram.astype(float) * 1.0 / histogram.max()


def circ_bit_shift(num, shift, bits):
    """ Circular bit-wise right shift. """
    val = num >> shift
    msb = num << (bits - shift)
    val = val | msb
    mask = 2 ** bits - 1
    return val & mask


def get_rotation_inv(num, bits):
    """ Gets rotation invariant value of num. """
    val = num
    for r in xrange(1, bits):
        rotated = circ_bit_shift(num, r, bits)
        if rotated < val:
            val = rotated
    return val


def count_transitions(num, bits):
    trans = num ^ (num >> 1)
    cnt = 0
    for i in xrange(0, bits - 1):
        if trans & (1 << i) != 0:
            cnt += 1
    return cnt


def get_unique_patterns(bits):
    """
    Puts together all possible unique (rotation invariant) LBP patterns for given number of bits.
    Returns the dict <pattern, index>, where the index specifies a bin in the histogram.
    """
    patterns = {}
    index = 0
    for num in xrange(0, 2 ** bits):
        unique_pattern = get_rotation_inv(num, bits)
        if unique_pattern not in patterns:
            patterns[unique_pattern] = index
            index += 1
    return patterns


def get_uniform_patterns(bits):
    """
    Puts together all possible uniform LBP patterns for given number of bits.
    The uniform pattern is rotation invariant and has two or less bit transitions.
    Returns the dict <pattern, index>, where the index specifies a bin in the histogram.
    """
    patterns = {}
    index = 0
    for num in xrange(0, 2 ** bits):
        unique_pattern = get_rotation_inv(num, bits)
        trans = count_transitions(unique_pattern, bits)
        if trans > 2:
            continue
        if unique_pattern not in patterns.has_key:
            patterns[unique_pattern] = index
            index += 1
    return patterns


def compare(img1, img2, step=5, radius=4, points=8, block=1, uniform=True, figure=True):
    """
    Computes a difference of two images as a norm between their LBP feature vectors.
    """

    if isinstance(img1, str):
        img1 = imgop.load_image(img1, True)
    if isinstance(img2, str):
        img2 = imgop.load_image(img2, True)

    if uniform:
        distrib = get_uniform_patterns(points)
    else:
        distrib = get_unique_patterns(points)

    # feature vectors
    img1f = feature(img1, distrib, step, radius, points, block)
    img2f = feature(img2, distrib, step, radius, points, block)

    df = np.linalg.norm(img1f - img2f)

    if figure:
        print df

        unique_patterns = sorted(distrib, key=distrib.get)

        # figures
        fig = plt.figure()
        plt.gray()

        show_image(fig.add_axes((0.0, 0.75, 0.2, 0.2)), img1)
        show_histogram(fig.add_axes((0.25, 0.6, 0.7, 0.35)), unique_patterns, img1f)

        show_image(fig.add_axes((0.0, 0.25, 0.2, 0.2)), img2)
        show_histogram(fig.add_axes((0.25, 0.1, 0.7, 0.35)), unique_patterns, img2f)

        plt.show()

    return df


def show_image(plot, img):
    plot.imshow(img)
    plot.get_xaxis().set_visible(False)
    plot.get_yaxis().set_visible(False)


def show_histogram(plot, x, y):
    ind = range(len(y))
    plot.bar(ind, y, align="center", width=1)
    plot.set_xticks(ind)
    plot.set_xticklabels(x, rotation="vertical")
    plot.set_xlim(-0.5, ind[-1] + 0.5)

#!/usr/bin/env python3

import sys
import os
import math
import numpy as np

import tensorflow as tf

from tensorflow.python.platform import gfile
from tensorflow.contrib.image.python.ops import distort_image_ops
from tensorflow.python.layers import utils


def _parse(record):
    feature_map = {
        'image/encoded':
        tf.FixedLenFeature([], dtype=tf.string, default_value=''),
        'image/class/label':
        tf.FixedLenFeature([1], dtype=tf.int64, default_value=-1),
        'image/class/text':
        tf.FixedLenFeature([], dtype=tf.string, default_value=''),
    }
    sparse_float32 = tf.VarLenFeature(dtype=tf.float32)
    feature_map.update({
        k: sparse_float32
        for k in [
            'image/object/bbox/xmin',
            'image/object/bbox/ymin',
            'image/object/bbox/xmax',
            'image/object/bbox/ymax',
        ]
    })
    features = tf.parse_single_example(record, feature_map)
    label = tf.cast(features['image/class/label'], dtype=tf.int64)
    xmin = tf.expand_dims(features['image/object/bbox/xmin'].values, 0)
    ymin = tf.expand_dims(features['image/object/bbox/ymin'].values, 0)
    xmax = tf.expand_dims(features['image/object/bbox/xmax'].values, 0)
    ymax = tf.expand_dims(features['image/object/bbox/ymax'].values, 0)
    bbox = tf.concat([ymin, xmin, ymax, xmax], 0)
    bbox = tf.expand_dims(bbox, 0)
    bbox = tf.transpose(bbox, [0, 2, 1])
    return features['image/encoded'], label, bbox, features['image/class/text']


def _decodejpeg(image_buffer, scope=None):
    """Decode a JPEG string into one 3-D float image Tensor.
    """
    with tf.name_scope(scope or '_decodejpeg'):
        image = tf.image.decode_jpeg(
            image_buffer,
            channels=3,
            fancy_upscaling=False,
            dct_method='INTEGER_FAST')
        return image


def _train_image(image_buffer, height, width, bbox, scope=None):
    """Distort one image for training a network."""

    with tf.name_scope(scope or 'train_image'):
        sample_distorted_bounding_box = tf.image.sample_distorted_bounding_box(
            tf.image.extract_jpeg_shape(image_buffer),
            bounding_boxes=bbox,
            min_object_covered=0.1,
            aspect_ratio_range=[0.75, 1.33],
            area_range=[0.05, 1.0],
            max_attempts=100,
            use_image_if_no_bounding_boxes=True)
        bbox_begin, bbox_size, distort_bbox = sample_distorted_bounding_box

        # Crop the image to the specified bounding box.
        offset_y, offset_x, _ = tf.unstack(bbox_begin)
        target_height, target_width, _ = tf.unstack(bbox_size)
        crop_window = tf.stack(
            [offset_y, offset_x, target_height, target_width])
        image = tf.image.decode_and_crop_jpeg(
            image_buffer, crop_window, channels=3)

        # Flip
        distorted_image = tf.image.random_flip_left_right(image)

        resize_method = tf.image.ResizeMethod.BILINEAR
        distorted_image = tf.image.resize_images(
            distorted_image, [height, width],
            resize_method,
            align_corners=False)

        # Restore the shape
        distorted_image.set_shape([height, width, 3])
        #More distortions...
        distorted_image = tf.cast(distorted_image, dtype=tf.float32)
        # Images values are expected to be in [0,1] for color distortion.
        distorted_image /= 255.
        # Randomly distort the colors.
        distorted_image = _distort_color(
            distorted_image, batch_position=0, distort_color_in_yiq=True)
        # Note: This ensures the scaling matches the output of eval_image
        distorted_image *= 255
        #More...

        distorted_image = tf.multiply(distorted_image, 1. / 127.5)
        distorted_image = tf.subtract(distorted_image, 1.0)
        # distorted_image = tf.transpose(distorted_image, [2, 0, 1])

        return distorted_image


def _distort_color(image,
                   batch_position=0,
                   distort_color_in_yiq=False,
                   scope=None):
    """Distort the color of the image."""
    with tf.name_scope(scope or 'distort_color'):

        def distort_fn_0(image=image):
            """Variant 0 of distort function."""
            image = tf.image.random_brightness(image, max_delta=32. / 255.)
            if distort_color_in_yiq:
                image = distort_image_ops.random_hsv_in_yiq(
                    image,
                    lower_saturation=0.5,
                    upper_saturation=1.5,
                    max_delta_hue=0.2 * math.pi)
            else:
                image = tf.image.random_saturation(image, lower=0.5, upper=1.5)
                image = tf.image.random_hue(image, max_delta=0.2)
            image = tf.image.random_contrast(image, lower=0.5, upper=1.5)
            return image

        def distort_fn_1(image=image):
            """Variant 1 of distort function."""
            image = tf.image.random_brightness(image, max_delta=32. / 255.)
            image = tf.image.random_contrast(image, lower=0.5, upper=1.5)
            if distort_color_in_yiq:
                image = distort_image_ops.random_hsv_in_yiq(
                    image,
                    lower_saturation=0.5,
                    upper_saturation=1.5,
                    max_delta_hue=0.2 * math.pi)
            else:
                image = tf.image.random_saturation(image, lower=0.5, upper=1.5)
                image = tf.image.random_hue(image, max_delta=0.2)
            return image

        image = utils.smart_cond(batch_position % 2 == 0, distort_fn_0,
                                 distort_fn_1)
        # The random_* ops do not necessarily clamp.
        image = tf.clip_by_value(image, 0.0, 1.0)
        return image


def _preprocess(imagebuffer, bbox, subset):
    # Assert subset is train
    image = _train_image(imagebuffer, 224, 224, bbox)
    return image

def get_labeled_images():
    prefix = ''

    file_url = 'https://kungfudata.blob.core.windows.net/data/imagenet/test-data'
    filename = os.path.join(prefix, 'test-data')
    file_sha1sum = '0d4ad2fb4a7edf902c78bf83755291dbc0a13e19'  # TODO: check sha1sum

    if not os.path.exists(filename):
        # TODO: down from file_url
        print('%s NOT exist, please download from %s' % (filename, file_url))
        exit(1)

    files = [
        filename,
    ]

    subset = "train"
    queue = tf.train.string_input_producer(files, shuffle=False)
    reader = tf.TFRecordReader()
    _, record = reader.read(queue)

    # Remove warnings using tf.data
    # dataset = tf.data.TFRecordDataset(files)
    # dataset = dataset.map(_parse, num_parallel_calls=tf.constant(1, dtype=tf.int32))
    # dataset = dataset.batch(32)
    #
    # iterator = dataset.make_one_shot_iterator()

    imagebuffer, label, bbox, _ = _parse(record)
    image = _preprocess(imagebuffer, bbox, subset)
    # print image
    images, labels = tf.train.batch([image, label],
                                    batch_size=32,
                                    num_threads=1,
                                    capacity=100)
    return images, labels

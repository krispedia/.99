# -*- coding: utf-8 -*-
"""detection_video.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1e36gww2Oge1ISNl1qHl7oVfgrtai6Dvu
"""
import os
import sys
import json
import datetime
import numpy as np
import skimage.draw
import random
import collections

# Root directory of the project
ROOT_DIR = os.path.abspath("./")
ROOT_VIDEO_DIR = os.path.abspath("./media")
print(ROOT_DIR)

# Import Mask RCNN
RCNN_ROOT_DIR = os.path.join(ROOT_DIR, "video\Mask_RCNN")
print(RCNN_ROOT_DIR)
sys.path.append(RCNN_ROOT_DIR)  # To find local version of the library

# Path to the dataset (note this is a shared images directory)

dataset_path = os.path.join(ROOT_VIDEO_DIR)
models_dir = os.path.join(RCNN_ROOT_DIR, "models")

print("base dataset dir:", dataset_path)
print("base models dir:", models_dir)

VIDEO_SAVE_DIR = os.path.join(dataset_path, "video_output")
VIDEO_FRAME_SAVE_DIR = os.path.join(VIDEO_SAVE_DIR, "video_frame")
print('video output dir :', VIDEO_SAVE_DIR)
print('frame output dir :', VIDEO_FRAME_SAVE_DIR)

weights_path = os.path.join(models_dir, 'init_weights\mask_rcnn_alcohol_0308.h5')
print("Using init weights: ", weights_path)

def learning(v):

    from mrcnn.config import Config
    from mrcnn import model as modellib, utils
    from mrcnn import visualize
    from mrcnn.visualize import display_images
    from mrcnn.model import log
    import det as det

    import imgaug as ia
    from imgaug import augmenters as iaa

    class InferenceConfig(det.DetConfig):
        GPU_COUNT = 1
        IMAGES_PER_GPU = 1

    # DB save variable
    global count_obj
    global total_obj
    global obj_sec
    # global title

    from keras import backend as K
    K.clear_session()

    from. import views

    videofile = str(v)
    print(videofile)

    # Directory to save logs and model checkpoints, if not provided
    # through the command line argument --logs
    # DEFAULT_LOGS_DIR = os.path.join(ROOT_DIR, "logs")

    # Commented out IPython magic to ensure Python compatibility.
    # for visualization
    # import matplotlib
    # import matplotlib.pyplot as plt
    # import matplotlib.patches as patches
    # import matplotlib.lines as lines
    # from matplotlib.patches import Polygon

    """
    # The imgaug library is pretty flexible and make different types of augmentation possible.
    # The deterministic setting is used because any spatial changes to the image must also be
    # done to the mask. There are also some augmentors that are unsafe to apply. From the mrcnn
    # library:
    # Augmentors that are safe to apply to masks:
    # ["Sequential", "SomeOf", "OneOf", "Sometimes","Fliplr",
    # "Flipud", "CropAndPad", "Affine", "PiecewiseAffine"]
    # Affine, has settings that are unsafe, so always
    # test your augmentation on masks
    """

    ia.seed(1)

    # http://imgaug.readthedocs.io/en/latest/source/augmenters.html#sequential
    seq_of_aug = iaa.Sequential([
        iaa.Crop(percent=(0, 0.1)),  # random crops

        # horizontally flip 50% of the images
        iaa.Fliplr(0.5),

        # Gaussian blur to 50% of the images
        # with random sigma between 0 and 0.5.
        iaa.Sometimes(0.5,
                      iaa.GaussianBlur(sigma=(0, 0.5))
                      ),

        # Strengthen or weaken the contrast in each image.
        iaa.ContrastNormalization((0.75, 1.5)),

        # Add gaussian noise.
        # For 50% of all images, we sample the noise once per pixel.
        # For the other 50% of all images, we sample the noise per pixel AND
        # channel. This can change the color (not only brightness) of the
        # pixels.
        iaa.AdditiveGaussianNoise(loc=0, scale=(0.0, 0.05 * 255), per_channel=0.5),

        # Make some images brighter and some darker.
        # In 20% of all cases, we sample the multiplier once per channel,
        # which can end up changing the color of the images.
        iaa.Multiply((0.8, 1.2), per_channel=0.2),

        # Apply affine transformations to each image.
        # Scale/zoom them from 90% 5o 110%
        # Translate/move them, rotate them
        # Shear them slightly -2 to 2 degrees.
        iaa.Affine(
            scale={"x": (0.9, 1.1), "y": (0.9, 1.1)},
            translate_percent={"x": (-0.2, 0.2), "y": (-0.2, 0.2)},
            rotate=(-5, 5),
            shear=(-2, 2)
        )
    ], random_order=True)  # apply augmenters in random order

    inf_config = InferenceConfig('alcohol', ['alcohol', 'boob', 'cigarette', 'knife', 'gun', 'mouth', 'hand'])
    inf_config.ACTIVATION = 'leakyrelu'
    inf_config.CLASS_NAMES.insert(0, 'BG')
    inf_config.DETECTION_MIN_CONFIDENCE = 0.75
    inf_config.display()

    import cv2
    import numpy as np

    def random_colors(N):
        np.random.seed(1)
        colors = [tuple(255 * np.random.rand(3)) for _ in range(N)]
        return colors

    def apply_mask(image, mask, color, alpha=0.5):
        """apply mask to image"""
        for n, c in enumerate(color):
            image[:, :, n] = np.where(
                mask == 1,
                image[:, :, n] * (1 - alpha) + alpha * c,
                image[:, :, n]
            )
        return image

    from PIL import Image, ImageDraw, ImageFont

    def display_instances(image, boxes, masks, class_ids, class_names,
                          scores, image_name, save_dir, title="",
                          figsize=(16, 16), ax=None,
                          show_mask=True, show_bbox=True,
                          colors=None, captions=None):
        """
        boxes: [num_instance, (y1, x1, y2, x2, class_id)] in image coordinates.
        masks: [height, width, num_instances]
        class_ids: [num_instances]
        class_names: list of class names of the dataset
        scores: (optional) confidence scores for each box
        title: (optional) Figure title
        show_mask, show_bbox: To show masks and bounding boxes or not
        figsize: (optional) the size of the image
        colors: (optional) An array or colors to use with each object
        captions: (optional) A list of strings to use as captions for each object
        """

        N = boxes.shape[0]
        colors = colors or random_colors(N)

        if not N:
            print("\n*** No instances in image %s to draw *** \n" % (image_name))
            masked_image = image.astype(np.uint8).copy()
            masked_image = Image.fromarray(masked_image)
            masked_image.save(os.path.join(save_dir, '%s' % (image_name)))
            return
        else:
            assert boxes.shape[0] == masks.shape[-1] == class_ids.shape[0]

        useful_mask_indices = []

        for i in range(N):
            # Generate random colors
            colors = colors or random_colors(N)

            if not np.any(boxes[i]):
                # Skip this instance. Has no bbox. Likely lost in image cropping.
                continue
            useful_mask_indices.append(i)

        masked_image = image.astype(np.uint8).copy()
        for index, value in enumerate(useful_mask_indices):
            class_id = class_ids[value]
            label = class_names[class_id]

            # Skip hand,mouth masking
            if (label == 'hand') or (label == 'mouth'):
                pass
            else:
                masked_image = apply_mask(masked_image, masks[:, :, value], colors[index])

        masked_image = Image.fromarray(masked_image)
        draw = ImageDraw.Draw(masked_image)
        colors = np.array(colors).astype(int) * 255

        for index, value in enumerate(useful_mask_indices):
            class_id = class_ids[value]
            score = scores[value]
            label = class_names[class_id]

            # hand, mouth disable and others able
            if (label == 'hand') or (label == 'mouth'):
                pass
            else:

                # object timeline
                if label in sec_object:
                    pass
                else:
                    sec_object.append(label)

                y1, x1, y2, x2 = boxes[value]
                color = tuple(colors[index])
                draw.rectangle((x1, y1, x2, y2), outline=color)

                # Label
                # font = ImageFont.truetype('/Library/Fonts/Arial.ttf', 15)
                draw.text((x1, y1), "%s %f" % (label, score), (255, 255, 255))

            masked_image.save(os.path.join(save_dir, '%s' % (image_name)))

    inf_model = modellib.MaskRCNN(mode="inference",
                                  config=inf_config,
                                  model_dir=models_dir)

    inf_config.display()

    inf_model.load_weights(weights_path, by_name=True)

    import os
    print(videofile)
    print(ROOT_VIDEO_DIR)
    video = cv2.VideoCapture(os.path.join(ROOT_VIDEO_DIR, videofile))

    # Find OpenCV version
    (major_ver, minor_ver, subminor_ver) = (cv2.__version__).split('.')

    if int(major_ver) < 3:
        fps = round(video.get(cv2.cv.CV_CAP_PROP_FPS))
        print("Frames per second using video.get(cv2.cv.CV_CAP_PROP_FPS): {0}".format(fps))
    else:
        fps = round(video.get(cv2.CAP_PROP_FPS))
        print("Frames per second using video.get(cv2.CAP_PROP_FPS) : {0}".format(fps))

    video.release()

    # Commented out IPython magic to ensure Python compatibility.

    import colorsys
    from skimage.measure import find_contours
    import datetime
    import time

    start = time.time()
    today_time = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
    makedir = os.path.join(VIDEO_FRAME_SAVE_DIR, today_time)
    print("frame make dir : ", makedir)
    os.mkdir(makedir)

    # title = ""
    # title = today_time

    capture = cv2.VideoCapture(os.path.join(ROOT_VIDEO_DIR, videofile))

    batch_size = 1
    frame_count = 0
    frame_obj = {}
    sec_object = []

    count_obj = {}
    total_obj = {}
    obj_sec = {}

    while True:
        ret, frame = capture.read()

        # print(ret, frame)
        # Bail out when the video file ends
        if not ret:
            print(ret)
            break
        # Save each frame of the video to a list
        frame_count += 1
        frame_sec = frame_count // fps
        print('frame :', frame_count)
        print('frame second :', frame_sec, 's')

        frames = []
        frames.append(frame)
        if len(frames) == batch_size:
            results = inf_model.detect(frames, verbose=0)
            for i, item in enumerate(zip(frames, results)):
                frame = item[0]
                r = item[1]
                name = '{0}.jpg'.format(frame_count + i - batch_size + 1)
                frame = display_instances(
                    frame, r['rois'], r['masks'], r['class_ids'], inf_config.CLASS_NAMES, r['scores'],
                    name, makedir,
                )

            # Clear the frames array to start the next batch
            frames = []
        if frame_count % fps == 0:
            frame_obj[frame_sec] = sec_object
            sec_object = []

    #keys and values in dictionary change
    for sec, values in frame_obj.items():
        for value in values:
            if value not in list(obj_sec.keys()):
                obj_sec[value] = [sec]
            else :
                obj_sec[value].append(sec)

    print('---------------object Timeline------------------')
    for key in obj_sec.keys():
        print("{} time line -> {}".format(key, obj_sec[key]))


    print('-----------------object ratio-------------------')
    for key in obj_sec.keys():
        ratio = round(len(obj_sec[key])/frame_sec * 100, 2)
        count_obj[key] = ratio
        print("{} ratio : {}".format(key, ratio))


    print('--------------Total object ratio-----------------')
    total_sec = len(obj_sec.keys())*frame_sec
    others_ratio = 0
    for key in obj_sec.keys():
        total_ratio = round(len(obj_sec[key]) /total_sec * 100, 2)
        total_obj[key] = total_ratio
        print("{} total ratio : {}".format(key, total_ratio))
        others_ratio += total_ratio

    others_ratio = round(100 - others_ratio, 2)
    total_obj['others'] = others_ratio
    print("others total ratio : {}".format(others_ratio))

    print('-------------------------------------------------')
    stop = time.time()
    print("time : {}s".format(round(stop - start, 2)))

    # Get all image file paths to a list.
    images = os.listdir(makedir)

    # Sort the images by name index.
    images = sorted(images, key=lambda x: float(os.path.split(x)[1][:-4]))
    print(images)

    def make_video(outvid, images=None, fps=30, size=None,
                   is_color=True, format="AVC1"):
        """
        Create a video from a list of images.

        @param      outvid      output video
        @param      images      list of images to use in the video
        @param      fps         frame per second
        @param      size        size of each frame
        @param      is_color    color
        @param      format      see http://www.fourcc.org/codecs.php
        @return                 see http://opencv-python-tutroals.readthedocs.org/en/latest/py_tutorials/py_gui/py_video_display/py_video_display.html
        """
        from cv2 import VideoWriter, VideoWriter_fourcc, imread, resize
        fourcc = VideoWriter_fourcc(*format)
        vid = None
        print('len(images):', len(images))

        for image in images:
            if not os.path.exists(image):
                raise FileNotFoundError(image)
            img = imread(image)
            if vid is None:
                if size is None:
                    size = img.shape[1], img.shape[0]
                vid = VideoWriter(outvid, fourcc, float(fps), size, is_color)
            if size[0] != img.shape[1] and size[1] != img.shape[0]:
                img = resize(img, size)
            vid.write(img)
        vid.release()
        return vid

    # Directory of images to run detection on
    # ROOT_DIR = os.getcwd()
    # VIDEO_DIR = os.path.join(ROOT_DIR, "videos")
    # VIDEO_SAVE_DIR = os.path.join(VIDEO_DIR, "save")

    images = os.listdir(makedir)
    # Sort the images by integer index
    images = sorted(images, key=lambda x: float(os.path.split(x)[1][:-4]))

    outvid = os.path.join(dataset_path, "{}".format(videofile))
    print("video file save dir :", outvid)

    os.chdir(makedir)
    make_video(outvid, images, fps)

    views.learning_check = True
